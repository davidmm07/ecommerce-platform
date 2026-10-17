from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ecommerce.application.errors import ConcurrentModification, DuplicateSku, RequestInProgress
from ecommerce.container import Container
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.order import Customer, Order, OrderLine, ShippingAddress
from ecommerce.domain.ordering.pricing import WeightBasedShipping
from tests.factories import NOW, make_product

FREE_SHIPPING = WeightBasedShipping(base_fee=Money.zero(), per_kg_fee=Money.zero())


async def test_products_round_trip_with_exact_values(clean_database: Container) -> None:
    product = make_product("WB-033", name="Water Bottle", price="24.99", weight_kg="0.450")
    async with clean_database.unit_of_work() as uow:
        await uow.products.add(product)
        await uow.commit()

    async with clean_database.unit_of_work() as uow:
        stored = await uow.products.get(product.id)

    assert stored is not None
    assert stored.price.amount == Decimal("24.99")
    assert stored.weight_kg == Decimal("0.450")
    assert stored.created_at == NOW
    assert stored.version == 1


async def test_active_skus_are_unique_but_archived_ones_can_be_reused(
    clean_database: Container,
) -> None:
    original = make_product("RS-001")
    async with clean_database.unit_of_work() as uow:
        await uow.products.add(original)
        await uow.commit()

    with pytest.raises(DuplicateSku) as caught:
        async with clean_database.unit_of_work() as uow:
            await uow.products.add(make_product("RS-001"))
    assert caught.value.sku == "RS-001"

    async with clean_database.unit_of_work() as uow:
        stored = await uow.products.get(original.id, lock=True)
        assert stored is not None
        stored.archive(NOW)
        await uow.products.update(stored)
        await uow.products.add(make_product("RS-001"))
        await uow.commit()

    async with clean_database.unit_of_work() as uow:
        assert await uow.products.get(original.id) is None
        archived = await uow.products.get_many([original.id], include_archived=True)
        assert archived[0].is_archived


async def test_concurrent_writers_are_detected(clean_database: Container) -> None:
    product = make_product(stock=10)
    async with clean_database.unit_of_work() as uow:
        await uow.products.add(product)
        await uow.commit()

    async with clean_database.unit_of_work() as slow, clean_database.unit_of_work() as fast:
        stale = await slow.products.get(product.id)
        fresh = await fast.products.get(product.id)
        assert stale is not None
        assert fresh is not None
        fresh.reserve(1, NOW)
        await fast.products.update(fresh)
        await fast.commit()
        stale.reserve(2, NOW)
        with pytest.raises(ConcurrentModification):
            await slow.products.update(stale)


async def test_database_constraints_back_up_the_domain(clean_database: Container) -> None:
    product = make_product(stock=1)
    async with clean_database.unit_of_work() as uow:
        await uow.products.add(product)
        await uow.commit()
    for statement in (
        "UPDATE products SET stock = -1",
        "UPDATE products SET price = 0",
        "UPDATE products SET category = 'spaceships'",
    ):
        with pytest.raises(IntegrityError):
            async with clean_database.engine.begin() as connection:
                await connection.execute(text(statement))


async def test_orders_round_trip_with_lines(clean_database: Container) -> None:
    product = make_product(stock=5)
    order = Order.place(
        order_id=uuid4(),
        customer=Customer.build(name="Ada", email="ada@example.com"),
        shipping_address=ShippingAddress.build(
            line1="1 Main St", city="Springfield", postal_code="12345", country="US"
        ),
        lines=[
            OrderLine(
                product_id=product.id,
                sku=product.sku.value,
                name=product.name,
                unit_price=product.price,
                quantity=2,
                unit_weight_kg=product.weight_kg,
            )
        ],
        shipping_policy=FREE_SHIPPING,
        idempotency_key="round-trip-key",
        request_fingerprint="a" * 64,
        now=NOW,
    )
    async with clean_database.unit_of_work() as uow:
        await uow.products.add(product)
        await uow.orders.add(order)
        await uow.commit()

    async with clean_database.unit_of_work() as uow:
        stored = await uow.orders.get_by_idempotency_key("round-trip-key")
        with pytest.raises(RequestInProgress):
            await uow.orders.add(
                Order.place(
                    order_id=uuid4(),
                    customer=order.customer,
                    shipping_address=order.shipping_address,
                    lines=order.lines,
                    shipping_policy=FREE_SHIPPING,
                    idempotency_key="round-trip-key",
                    request_fingerprint="a" * 64,
                    now=NOW,
                )
            )

    assert stored is not None
    assert stored.number == order.number
    assert stored.lines == order.lines
    assert stored.totals == order.totals
