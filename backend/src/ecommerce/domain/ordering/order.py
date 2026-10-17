from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from ecommerce.domain.errors import FieldErrors, InvalidValue
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.errors import InvalidOrderTransition
from ecommerce.domain.ordering.pricing import OrderTotals, ShippingPolicy, calculate_totals
from ecommerce.domain.text import single_line

MAX_QUANTITY_PER_LINE = 100
MAX_LINES_PER_ORDER = 50
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_POSTAL_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{1,14}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"


@dataclass(frozen=True, slots=True)
class Customer:
    name: str
    email: str

    @classmethod
    def build(cls, *, name: str, email: str) -> Customer:
        errors = FieldErrors()
        with errors.collect("name"):
            clean_name = single_line(name, max_length=120)
        with errors.collect("email"):
            clean_email = _clean_email(email)
        errors.raise_if_any()
        return cls(name=clean_name, email=clean_email)


@dataclass(frozen=True, slots=True)
class ShippingAddress:
    line1: str
    city: str
    postal_code: str
    country: str

    @classmethod
    def build(cls, *, line1: str, city: str, postal_code: str, country: str) -> ShippingAddress:
        errors = FieldErrors()
        with errors.collect("line1"):
            clean_line1 = single_line(line1, max_length=200)
        with errors.collect("city"):
            clean_city = single_line(city, max_length=100)
        with errors.collect("postal_code"):
            clean_postal_code = _clean_postal_code(postal_code)
        with errors.collect("country"):
            clean_country = _clean_country(country)
        errors.raise_if_any()
        return cls(
            line1=clean_line1, city=clean_city, postal_code=clean_postal_code, country=clean_country
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderLine:
    product_id: UUID
    sku: str
    name: str
    unit_price: Money
    quantity: int
    unit_weight_kg: Decimal

    def __post_init__(self) -> None:
        if not 1 <= self.quantity <= MAX_QUANTITY_PER_LINE:
            raise InvalidValue(f"quantity must be between 1 and {MAX_QUANTITY_PER_LINE}")

    @property
    def line_total(self) -> Money:
        return self.unit_price * self.quantity

    @property
    def line_weight_kg(self) -> Decimal:
        return self.unit_weight_kg * self.quantity


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentSummary:
    card_brand: str
    card_last4: str
    reference: str | None = None
    failure_code: str | None = None


@dataclass(slots=True, eq=False, kw_only=True)
class Order:
    id: UUID
    number: str
    status: OrderStatus
    customer: Customer
    shipping_address: ShippingAddress
    lines: tuple[OrderLine, ...]
    totals: OrderTotals
    idempotency_key: str
    request_fingerprint: str
    created_at: datetime
    updated_at: datetime
    payment: PaymentSummary | None = None
    version: int = 1

    @classmethod
    def place(
        cls,
        *,
        order_id: UUID,
        customer: Customer,
        shipping_address: ShippingAddress,
        lines: Sequence[OrderLine],
        shipping_policy: ShippingPolicy,
        idempotency_key: str,
        request_fingerprint: str,
        now: datetime,
    ) -> Order:
        _ensure_valid_lines(lines)
        return cls(
            id=order_id,
            number=order_number_for(order_id),
            status=OrderStatus.PENDING_PAYMENT,
            customer=customer,
            shipping_address=shipping_address,
            lines=tuple(lines),
            totals=calculate_totals(lines, shipping_policy),
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            created_at=now,
            updated_at=now,
        )

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    def mark_paid(self, payment: PaymentSummary, now: datetime) -> None:
        self._transition_to(OrderStatus.PAID, now)
        self.payment = payment

    def mark_payment_failed(self, payment: PaymentSummary, now: datetime) -> None:
        self._transition_to(OrderStatus.PAYMENT_FAILED, now)
        self.payment = payment

    def _transition_to(self, target: OrderStatus, now: datetime) -> None:
        if self.status is not OrderStatus.PENDING_PAYMENT:
            raise InvalidOrderTransition(self.status.value, target.value)
        self.status = target
        self.updated_at = now


def order_number_for(order_id: UUID) -> str:
    value = order_id.int & ((1 << 60) - 1)
    symbols = []
    for _ in range(12):
        symbols.append(_CROCKFORD[value & 31])
        value >>= 5
    return "ORD-" + "".join(reversed(symbols))


def _ensure_valid_lines(lines: Sequence[OrderLine]) -> None:
    if not lines:
        raise InvalidValue("an order needs at least one line")
    if len(lines) > MAX_LINES_PER_ORDER:
        raise InvalidValue(f"an order can have at most {MAX_LINES_PER_ORDER} lines")
    if len({line.product_id for line in lines}) != len(lines):
        raise InvalidValue("each product can appear only once per order")


def _clean_email(raw: str) -> str:
    email = raw.strip().lower()
    if not email:
        raise InvalidValue("is required")
    if len(email) > 254 or not _EMAIL.fullmatch(email):
        raise InvalidValue("must be a valid email address")
    return email


def _clean_postal_code(raw: str) -> str:
    postal_code = " ".join(raw.split()).upper()
    if not postal_code:
        raise InvalidValue("is required")
    if not _POSTAL_CODE.fullmatch(postal_code):
        raise InvalidValue("must be 2 to 15 letters, digits, spaces or hyphens")
    return postal_code


def _clean_country(raw: str) -> str:
    country = raw.strip().upper()
    if not _COUNTRY.fullmatch(country):
        raise InvalidValue("must be an ISO 3166-1 alpha-2 code, e.g. US")
    return country
