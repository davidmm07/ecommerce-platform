from uuid import uuid4

import pytest

from ecommerce.application.errors import (
    IdempotencyKeyReused,
    NotFoundError,
    PaymentDeclined,
    PaymentUnavailable,
    RequestInProgress,
)
from ecommerce.application.ordering.cart import QuoteCart
from ecommerce.application.ordering.commands import CartItem
from ecommerce.application.ordering.place_order import PlaceOrder
from ecommerce.application.ordering.queries import GetOrder, ListOrders
from ecommerce.application.pagination import Page, PageRequest
from ecommerce.application.ports.payments import PaymentGatewayError
from ecommerce.domain.catalog.errors import InsufficientStock
from ecommerce.domain.errors import DomainValidationError
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.order import Order, OrderStatus
from ecommerce.domain.ordering.pricing import FreeShippingOverThreshold, WeightBasedShipping
from tests.factories import FixedClock, make_product, order_command
from tests.fakes import FakePaymentGateway, InMemoryDatabase, InMemoryUnitOfWork

SHIPPING = FreeShippingOverThreshold(
    inner=WeightBasedShipping(base_fee=Money.of("4.99"), per_kg_fee=Money.of("1.25")),
    threshold=Money.of("100.00"),
)


def place_order(database: InMemoryDatabase, gateway: FakePaymentGateway) -> PlaceOrder:
    return PlaceOrder(
        uow_factory=lambda: InMemoryUnitOfWork(database),
        payment_gateway=gateway,
        shipping_policy=SHIPPING,
        clock=FixedClock(),
        new_id=uuid4,
    )


@pytest.fixture
def database() -> InMemoryDatabase:
    return InMemoryDatabase()


async def test_successful_checkout_reserves_stock_and_marks_the_order_paid(
    database: InMemoryDatabase,
) -> None:
    shoes = make_product("RS-001", price="89.99", stock=5, weight_kg="0.350")
    mug = make_product("TM-029", price="16.99", stock=2, weight_kg="0.300")
    database.seed(shoes, mug)
    gateway = FakePaymentGateway()

    result = await place_order(database, gateway).execute(
        order_command([(shoes.id, 1), (mug.id, 2)])
    )

    order = result.order
    assert not result.replayed
    assert order.status is OrderStatus.PAID
    assert order.totals.subtotal == Money.of("123.97")
    assert order.totals.shipping.is_zero
    assert order.payment is not None
    assert (order.payment.card_last4, order.payment.reference) == ("4242", "fake_1")
    assert database.product(shoes.id).stock == 4
    assert database.product(mug.id).stock == 0
    assert gateway.requests[0].amount == Money.of("123.97")
    assert gateway.requests[0].reference == order.number


async def test_duplicate_cart_lines_are_merged(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5, price="10.00")
    database.seed(shoes)
    result = await place_order(database, FakePaymentGateway()).execute(
        order_command([(shoes.id, 1), (shoes.id, 2)])
    )
    assert [(line.sku, line.quantity) for line in result.order.lines] == [("RS-001", 3)]
    assert result.order.totals.shipping == Money.of("7.49")


async def test_declined_payment_releases_the_stock(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)

    with pytest.raises(PaymentDeclined) as caught:
        await place_order(database, FakePaymentGateway(decline_code="insufficient_funds")).execute(
            order_command([(shoes.id, 2)])
        )

    order = database.orders[caught.value.order_id]
    assert order.status is OrderStatus.PAYMENT_FAILED
    assert order.payment is not None
    assert order.payment.failure_code == "insufficient_funds"
    assert database.product(shoes.id).stock == 5
    assert caught.value.details()["decline_code"] == "insufficient_funds"


async def test_provider_outage_fails_the_order_without_losing_stock(
    database: InMemoryDatabase,
) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    gateway = FakePaymentGateway(error=PaymentGatewayError("down"))

    with pytest.raises(PaymentUnavailable) as caught:
        await place_order(database, gateway).execute(order_command([(shoes.id, 1)]))

    order = database.orders[caught.value.order_id]
    assert order.payment is not None
    assert order.payment.failure_code == "processing_error"
    assert database.product(shoes.id).stock == 5


async def test_not_enough_stock_reports_every_short_line(database: InMemoryDatabase) -> None:
    shoes = make_product("RS-001", stock=1)
    mug = make_product("TM-029", stock=0)
    database.seed(shoes, mug)
    gateway = FakePaymentGateway()

    with pytest.raises(InsufficientStock) as caught:
        await place_order(database, gateway).execute(order_command([(shoes.id, 2), (mug.id, 1)]))

    assert [shortage.sku for shortage in caught.value.shortages] == ["RS-001", "TM-029"]
    assert gateway.requests == []
    assert database.orders == {}


async def test_unknown_products_are_not_found(database: InMemoryDatabase) -> None:
    with pytest.raises(NotFoundError):
        await place_order(database, FakePaymentGateway()).execute(order_command([(uuid4(), 1)]))


async def test_replaying_the_same_request_returns_the_original_order(
    database: InMemoryDatabase,
) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    gateway = FakePaymentGateway()
    use_case = place_order(database, gateway)
    command = order_command([(shoes.id, 1)], key="same-key-123")

    first = await use_case.execute(command)
    second = await use_case.execute(command)

    assert second.replayed
    assert second.order.id == first.order.id
    assert len(gateway.requests) == 1
    assert database.product(shoes.id).stock == 4


async def test_reusing_a_key_with_a_different_body_is_rejected(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    use_case = place_order(database, FakePaymentGateway())
    await use_case.execute(order_command([(shoes.id, 1)], key="same-key-123"))
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(order_command([(shoes.id, 2)], key="same-key-123"))


async def test_replaying_a_declined_request_declines_again(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    gateway = FakePaymentGateway(decline_code="card_declined")
    use_case = place_order(database, gateway)
    command = order_command([(shoes.id, 1)], key="declined-key-1")
    with pytest.raises(PaymentDeclined):
        await use_case.execute(command)
    with pytest.raises(PaymentDeclined):
        await use_case.execute(command)
    assert len(gateway.requests) == 1


async def test_a_pending_order_with_the_same_key_is_still_in_progress(
    database: InMemoryDatabase,
) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    command = order_command([(shoes.id, 1)], key="pending-key-1")
    use_case = place_order(database, FakePaymentGateway())
    await use_case.execute(command)
    order = next(iter(database.orders.values()))
    order.status = OrderStatus.PENDING_PAYMENT
    with pytest.raises(RequestInProgress):
        await use_case.execute(command)


async def test_validates_the_whole_request_before_touching_stock(
    database: InMemoryDatabase,
) -> None:
    command = order_command([], key="bad", card_number="1234", email="nope")
    with pytest.raises(DomainValidationError) as caught:
        await place_order(database, FakePaymentGateway()).execute(command)
    assert {error.field for error in caught.value.errors} == {
        "idempotency_key",
        "items",
        "customer.email",
        "payment.card_number",
    }


async def test_quantity_limits_apply_per_line_and_per_product(database: InMemoryDatabase) -> None:
    product_id = uuid4()
    with pytest.raises(DomainValidationError) as caught:
        await place_order(database, FakePaymentGateway()).execute(
            order_command([(product_id, 0), (product_id, 101)])
        )
    assert [error.field for error in caught.value.errors] == [
        "items[0].quantity",
        "items[1].quantity",
    ]
    with pytest.raises(DomainValidationError, match="must not exceed 100"):
        await place_order(database, FakePaymentGateway()).execute(
            order_command([(product_id, 60), (product_id, 60)])
        )


async def test_quote_prices_the_cart_without_reserving(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5, price="20.00", weight_kg="1.200")
    database.seed(shoes)
    quote = await QuoteCart(
        uow_factory=lambda: InMemoryUnitOfWork(database), shipping_policy=SHIPPING
    ).execute([CartItem(shoes.id, 2)])
    assert quote.totals.total == Money.of("48.74")
    assert database.product(shoes.id).stock == 5
    assert database.commits == 0


async def test_get_and_list_orders(database: InMemoryDatabase) -> None:
    shoes = make_product(stock=5)
    database.seed(shoes)
    placed = await place_order(database, FakePaymentGateway()).execute(
        order_command([(shoes.id, 1)])
    )
    found = await GetOrder(uow_factory=lambda: InMemoryUnitOfWork(database)).execute(
        placed.order.id
    )
    assert found.number == placed.order.number
    with pytest.raises(NotFoundError):
        await GetOrder(uow_factory=lambda: InMemoryUnitOfWork(database)).execute(uuid4())

    emails: list[str | None] = []

    class StubOrders:
        async def list_page(self, request: PageRequest, *, email: str | None = None) -> Page[Order]:
            emails.append(email)
            return Page(items=[found], total=1, request=request)

    page = await ListOrders(orders=StubOrders()).execute(PageRequest(), email="  ADA@example.com ")
    assert page.items == [found]
    assert emails == ["ada@example.com"]
