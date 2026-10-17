from dataclasses import dataclass
from typing import Protocol

from ecommerce.domain.money import Money
from ecommerce.domain.payments.card import PaymentCard


@dataclass(frozen=True, slots=True, kw_only=True)
class ChargeRequest:
    amount: Money
    card: PaymentCard
    reference: str
    idempotency_key: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ChargeResult:
    approved: bool
    card_brand: str
    card_last4: str
    reference: str | None = None
    decline_code: str | None = None


class PaymentGatewayError(Exception):
    pass


class PaymentGateway(Protocol):
    async def charge(self, request: ChargeRequest) -> ChargeResult: ...
