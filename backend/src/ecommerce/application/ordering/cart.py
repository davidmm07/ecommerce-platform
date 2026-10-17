from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from ecommerce.application.errors import NotFoundError
from ecommerce.application.ordering.commands import CartItem
from ecommerce.application.ports.unit_of_work import UnitOfWorkFactory
from ecommerce.domain.catalog.errors import InsufficientStock, StockShortage
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.errors import FieldErrors
from ecommerce.domain.ordering.order import MAX_LINES_PER_ORDER, MAX_QUANTITY_PER_LINE, OrderLine
from ecommerce.domain.ordering.pricing import OrderTotals, ShippingPolicy, calculate_totals


@dataclass(frozen=True, slots=True)
class CartQuote:
    lines: tuple[OrderLine, ...]
    totals: OrderTotals


class QuoteCart:
    def __init__(self, *, uow_factory: UnitOfWorkFactory, shipping_policy: ShippingPolicy) -> None:
        self._uow_factory = uow_factory
        self._shipping_policy = shipping_policy

    async def execute(self, items: Sequence[CartItem]) -> CartQuote:
        normalized = normalize_items(items)
        async with self._uow_factory() as uow:
            products = await uow.products.get_many([item.product_id for item in normalized])
        lines = price_lines(normalized, products)
        return CartQuote(lines=lines, totals=calculate_totals(lines, self._shipping_policy))


def normalize_items(items: Sequence[CartItem]) -> tuple[CartItem, ...]:
    errors = FieldErrors()
    if not items:
        errors.add("items", "must contain at least one product")
    merged: dict[UUID, int] = {}
    for index, item in enumerate(items):
        if not 1 <= item.quantity <= MAX_QUANTITY_PER_LINE:
            errors.add(f"items[{index}].quantity", f"must be between 1 and {MAX_QUANTITY_PER_LINE}")
        merged[item.product_id] = merged.get(item.product_id, 0) + item.quantity
    if len(merged) > MAX_LINES_PER_ORDER:
        errors.add("items", f"must contain at most {MAX_LINES_PER_ORDER} different products")
    errors.raise_if_any()
    for product_id, quantity in merged.items():
        if quantity > MAX_QUANTITY_PER_LINE:
            errors.add(
                "items",
                f"the total quantity of product {product_id} must not exceed "
                f"{MAX_QUANTITY_PER_LINE}",
            )
    errors.raise_if_any()
    return tuple(CartItem(product_id, quantity) for product_id, quantity in merged.items())


def price_lines(items: Sequence[CartItem], products: Sequence[Product]) -> tuple[OrderLine, ...]:
    by_id = {product.id: product for product in products}
    for item in items:
        if item.product_id not in by_id:
            raise NotFoundError("Product", item.product_id)
    shortages = tuple(
        StockShortage(product.sku.value, item.quantity, product.stock)
        for item in items
        if (product := by_id[item.product_id]).stock < item.quantity
    )
    if shortages:
        raise InsufficientStock(shortages)
    return tuple(_line_for(by_id[item.product_id], item.quantity) for item in items)


def _line_for(product: Product, quantity: int) -> OrderLine:
    return OrderLine(
        product_id=product.id,
        sku=product.sku.value,
        name=product.name,
        unit_price=product.price,
        quantity=quantity,
        unit_weight_kg=product.weight_kg,
    )
