from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CartItem:
    product_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CustomerInput:
    name: str
    email: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AddressInput:
    line1: str
    city: str
    postal_code: str
    country: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CardInput:
    number: str = field(repr=False)
    expiry_month: int
    expiry_year: int
    cvc: str = field(repr=False)
    holder_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderCommand:
    idempotency_key: str
    items: tuple[CartItem, ...]
    customer: CustomerInput
    shipping_address: AddressInput
    card: CardInput
