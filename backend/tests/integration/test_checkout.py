import asyncio
from uuid import UUID

from ecommerce.application.errors import PaymentDeclined, RequestInProgress
from ecommerce.application.ordering.place_order import PlaceOrderResult
from ecommerce.container import Container
from ecommerce.domain.catalog.errors import InsufficientStock
from ecommerce.domain.ordering.order import OrderStatus
from ecommerce.infrastructure.payments.simulated import FLAKY_CARD
from tests.factories import make_product, order_command


async def seed(container: Container, stock: int) -> UUID:
    product = make_product(stock=stock)
    async with container.unit_of_work() as uow:
        await uow.products.add(product)
        await uow.commit()
    return product.id


async def stock_of(container: Container, product_id: UUID) -> int:
    async with container.unit_of_work() as uow:
        product = await uow.products.get(product_id)
    assert product is not None
    return product.stock


async def test_concurrent_checkouts_never_oversell(clean_database: Container) -> None:
    product_id = await seed(clean_database, stock=3)
    commands = [order_command([(product_id, 1)], key=f"race-key-{i:04d}") for i in range(10)]

    results = await asyncio.gather(
        *(clean_database.place_order.execute(command) for command in commands),
        return_exceptions=True,
    )

    paid = [r for r in results if isinstance(r, PlaceOrderResult)]
    sold_out = [r for r in results if isinstance(r, InsufficientStock)]
    assert (len(paid), len(sold_out)) == (3, 7)
    assert all(r.order.status is OrderStatus.PAID for r in paid)
    assert await stock_of(clean_database, product_id) == 0


async def test_concurrent_retries_with_one_key_create_one_order(clean_database: Container) -> None:
    product_id = await seed(clean_database, stock=10)
    command = order_command([(product_id, 1)], key="double-click-key")

    results = await asyncio.gather(
        *(clean_database.place_order.execute(command) for _ in range(5)),
        return_exceptions=True,
    )

    orders = {r.order.id for r in results if isinstance(r, PlaceOrderResult)}
    unexpected = [r for r in results if not isinstance(r, PlaceOrderResult | RequestInProgress)]
    assert len(orders) == 1
    assert unexpected == []
    assert await stock_of(clean_database, product_id) == 9


async def test_declined_payment_is_compensated_in_the_database(clean_database: Container) -> None:
    product_id = await seed(clean_database, stock=2)
    command = order_command([(product_id, 2)], key="declined-0001", card_number="4000000000000002")

    try:
        await clean_database.place_order.execute(command)
    except PaymentDeclined as declined:
        order = await clean_database.get_order.execute(declined.order_id)
    else:
        raise AssertionError

    assert order.status is OrderStatus.PAYMENT_FAILED
    assert await stock_of(clean_database, product_id) == 2


async def test_transient_provider_errors_are_retried(clean_database: Container) -> None:
    product_id = await seed(clean_database, stock=1)
    result = await clean_database.place_order.execute(
        order_command([(product_id, 1)], key="flaky-0001", card_number=FLAKY_CARD)
    )
    assert result.order.status is OrderStatus.PAID
