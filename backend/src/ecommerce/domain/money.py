from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ecommerce.domain.errors import InvalidValue

CENT = Decimal("0.01")
DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise InvalidValue("must be a finite decimal amount")
        if self.amount != self.amount.quantize(CENT):
            raise InvalidValue("must have at most 2 decimal places")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise InvalidValue("currency must be an ISO 4217 code")
        object.__setattr__(self, "amount", self.amount.quantize(CENT))

    @classmethod
    def of(cls, value: Decimal | int | str, currency: str = DEFAULT_CURRENCY) -> Money:
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise InvalidValue("must be a decimal amount") from exc
        return cls(amount, currency)

    @classmethod
    def rounded(cls, value: Decimal, currency: str = DEFAULT_CURRENCY) -> Money:
        return cls(value.quantize(CENT, rounding=ROUND_HALF_UP), currency)

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Money:
        return cls(Decimal("0.00"), currency)

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __add__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, quantity: int) -> Money:
        return Money(self.amount * quantity, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount >= other.amount

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def _ensure_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise InvalidValue(f"cannot combine {self.currency} with {other.currency}")
