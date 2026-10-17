from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from ecommerce.domain.errors import FieldErrors, InvalidValue
from ecommerce.domain.text import single_line

_SEPARATORS = re.compile(r"[\s-]")
_CVC = re.compile(r"^\d{3,4}$")


class CardBrand(StrEnum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentCard:
    number: str = field(repr=False)
    expiry_month: int
    expiry_year: int
    cvc: str = field(repr=False)
    holder_name: str

    @classmethod
    def parse(
        cls, *, number: str, expiry_month: int, expiry_year: int, cvc: str, holder_name: str
    ) -> PaymentCard:
        errors = FieldErrors()
        with errors.collect("card_number"):
            clean_number = _clean_number(number)
        with errors.collect("expiry_month"):
            if not 1 <= expiry_month <= 12:
                raise InvalidValue("must be between 1 and 12")
        with errors.collect("expiry_year"):
            if not 2000 <= expiry_year <= 2100:
                raise InvalidValue("must be a four digit year")
        with errors.collect("cvc"):
            if not _CVC.fullmatch(cvc.strip()):
                raise InvalidValue("must be 3 or 4 digits")
        with errors.collect("holder_name"):
            clean_holder = single_line(holder_name, max_length=100)
        errors.raise_if_any()
        return cls(
            number=clean_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvc=cvc.strip(),
            holder_name=clean_holder,
        )

    @property
    def last4(self) -> str:
        return self.number[-4:]

    @property
    def brand(self) -> CardBrand:
        return brand_of(self.number)

    def is_expired(self, today: date) -> bool:
        return (self.expiry_year, self.expiry_month) < (today.year, today.month)


def brand_of(number: str) -> CardBrand:
    if number.startswith("4"):
        return CardBrand.VISA
    if number[:2] in {"34", "37"}:
        return CardBrand.AMEX
    if 51 <= int(number[:2]) <= 55 or 2221 <= int(number[:4]) <= 2720:
        return CardBrand.MASTERCARD
    if number.startswith(("6011", "65")):
        return CardBrand.DISCOVER
    return CardBrand.UNKNOWN


def passes_luhn(number: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _clean_number(raw: str) -> str:
    number = _SEPARATORS.sub("", raw)
    if not number:
        raise InvalidValue("is required")
    if not (number.isascii() and number.isdigit()) or not 12 <= len(number) <= 19:
        raise InvalidValue("must be 12 to 19 digits")
    if not passes_luhn(number):
        raise InvalidValue("is not a valid card number")
    return number
