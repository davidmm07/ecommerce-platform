from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.errors import InsufficientStock, ProductUnavailable, StockShortage
from ecommerce.domain.catalog.image import ProductImage
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import FieldErrors, InvalidValue
from ecommerce.domain.money import DEFAULT_CURRENCY, Money
from ecommerce.domain.text import multi_line, single_line

NAME_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000
MAX_PRICE = Decimal("1000000.00")
MAX_STOCK = 1_000_000
MAX_WEIGHT_KG = Decimal("1000.000")
WEIGHT_STEP = Decimal("0.001")


def clean_name(value: str) -> str:
    return single_line(value, max_length=NAME_MAX_LENGTH)


def clean_description(value: str) -> str:
    return multi_line(value, max_length=DESCRIPTION_MAX_LENGTH)


def check_price(value: Decimal, currency: str = DEFAULT_CURRENCY) -> Money:
    price = Money.of(value, currency)
    if price.amount <= 0:
        raise InvalidValue("must be greater than 0")
    if price.amount > MAX_PRICE:
        raise InvalidValue(f"must not exceed {MAX_PRICE}")
    return price


def check_stock(value: int) -> int:
    if value < 0:
        raise InvalidValue("must not be negative")
    if value > MAX_STOCK:
        raise InvalidValue(f"must not exceed {MAX_STOCK}")
    return value


def check_weight(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise InvalidValue("must be a finite number")
    if value < 0:
        raise InvalidValue("must not be negative")
    if value > MAX_WEIGHT_KG:
        raise InvalidValue(f"must not exceed {MAX_WEIGHT_KG}")
    if value != value.quantize(WEIGHT_STEP):
        raise InvalidValue("must have at most 3 decimal places")
    return value.quantize(WEIGHT_STEP)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductDetails:
    name: str
    description: str
    category: Category
    price: Money
    stock: int
    weight_kg: Decimal

    @classmethod
    def build(
        cls,
        *,
        name: str,
        description: str,
        category: Category | str,
        price: Decimal,
        stock: int,
        weight_kg: Decimal,
        currency: str = DEFAULT_CURRENCY,
    ) -> ProductDetails:
        errors = FieldErrors()
        with errors.collect("name"):
            clean_product_name = clean_name(name)
        with errors.collect("description"):
            clean_product_description = clean_description(description)
        with errors.collect("category"):
            product_category = (
                category if isinstance(category, Category) else Category.parse(category)
            )
        with errors.collect("price"):
            product_price = check_price(price, currency)
        with errors.collect("stock"):
            product_stock = check_stock(stock)
        with errors.collect("weight_kg"):
            product_weight = check_weight(weight_kg)
        errors.raise_if_any()
        return cls(
            name=clean_product_name,
            description=clean_product_description,
            category=product_category,
            price=product_price,
            stock=product_stock,
            weight_kg=product_weight,
        )


@dataclass(slots=True, eq=False, kw_only=True)
class Product:
    id: UUID
    sku: Sku
    name: str
    description: str
    category: Category
    price: Money
    stock: int
    weight_kg: Decimal
    created_at: datetime
    updated_at: datetime
    version: int = 1
    archived_at: datetime | None = None
    image: ProductImage | None = None

    @classmethod
    def create(
        cls, *, product_id: UUID, sku: Sku, details: ProductDetails, now: datetime
    ) -> Product:
        return cls(
            id=product_id,
            sku=sku,
            name=details.name,
            description=details.description,
            category=details.category,
            price=details.price,
            stock=details.stock,
            weight_kg=details.weight_kg,
            created_at=now,
            updated_at=now,
        )

    @property
    def details(self) -> ProductDetails:
        return ProductDetails(
            name=self.name,
            description=self.description,
            category=self.category,
            price=self.price,
            stock=self.stock,
            weight_kg=self.weight_kg,
        )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    def revise(self, details: ProductDetails, now: datetime) -> bool:
        self._ensure_active()
        if details == self.details:
            return False
        self.name = details.name
        self.description = details.description
        self.category = details.category
        self.price = details.price
        self.stock = details.stock
        self.weight_kg = details.weight_kg
        self.updated_at = now
        return True

    def reserve(self, quantity: int, now: datetime) -> None:
        self._ensure_active()
        _ensure_positive(quantity)
        if quantity > self.stock:
            raise InsufficientStock((StockShortage(self.sku.value, quantity, self.stock),))
        self.stock -= quantity
        self.updated_at = now

    def release(self, quantity: int, now: datetime) -> None:
        _ensure_positive(quantity)
        self.stock += quantity
        self.updated_at = now

    def replace_image(self, image: ProductImage, now: datetime) -> ProductImage | None:
        self._ensure_active()
        previous = self.image
        self.image = image
        self.updated_at = now
        return previous

    def remove_image(self, now: datetime) -> ProductImage | None:
        self._ensure_active()
        previous = self.image
        if previous is not None:
            self.image = None
            self.updated_at = now
        return previous

    def archive(self, now: datetime) -> None:
        if self.archived_at is None:
            self.archived_at = now
            self.updated_at = now

    def _ensure_active(self) -> None:
        if self.archived_at is not None:
            raise ProductUnavailable(self.sku.value)


def _ensure_positive(quantity: int) -> None:
    if quantity <= 0:
        raise InvalidValue("quantity must be greater than 0")
