from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from ecommerce.application.ordering.commands import (
    AddressInput,
    CardInput,
    CartItem,
    CustomerInput,
    PlaceOrderCommand,
)
from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.product import Product, ProductDetails
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.money import Money

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
APPROVED_CARD = "4242424242424242"


class FixedClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


def product_details(
    *,
    name: str = "Running Shoes",
    description: str = "Lightweight running shoes for daily training",
    category: Category = Category.FOOTWEAR,
    price: str = "89.99",
    stock: int = 10,
    weight_kg: str = "0.350",
) -> ProductDetails:
    return ProductDetails(
        name=name,
        description=description,
        category=category,
        price=Money(Decimal(price)),
        stock=stock,
        weight_kg=Decimal(weight_kg),
    )


def make_product(
    sku: str = "RS-001",
    *,
    name: str = "Running Shoes",
    category: Category = Category.FOOTWEAR,
    price: str = "89.99",
    stock: int = 10,
    weight_kg: str = "0.350",
) -> Product:
    details = product_details(
        name=name, category=category, price=price, stock=stock, weight_kg=weight_kg
    )
    return Product.create(product_id=uuid4(), sku=Sku(sku), details=details, now=NOW)


def order_command(
    items: list[tuple[UUID, int]],
    *,
    key: str = "checkout-0001",
    card_number: str = APPROVED_CARD,
    email: str = "ada@example.com",
    expiry_year: int = 2030,
) -> PlaceOrderCommand:
    return PlaceOrderCommand(
        idempotency_key=key,
        items=tuple(CartItem(product_id, quantity) for product_id, quantity in items),
        customer=CustomerInput(name="Ada Lovelace", email=email),
        shipping_address=AddressInput(
            line1="221B Baker Street", city="London", postal_code="NW1 6XE", country="GB"
        ),
        card=CardInput(
            number=card_number,
            expiry_month=12,
            expiry_year=expiry_year,
            cvc="123",
            holder_name="Ada Lovelace",
        ),
    )
