from decimal import Decimal

import pytest

from ecommerce.domain.errors import InvalidValue
from ecommerce.domain.money import Money


def test_normalizes_amount_to_two_decimals() -> None:
    assert Money(Decimal("5")).amount == Decimal("5.00")
    assert str(Money.of("19.9")) == "19.90 USD"


@pytest.mark.parametrize("raw", ["19.999", "NaN", "Infinity", "abc", ""])
def test_rejects_amounts_that_are_not_money(raw: str) -> None:
    with pytest.raises(InvalidValue):
        Money.of(raw)


def test_rejects_invalid_currency_codes() -> None:
    with pytest.raises(InvalidValue, match="ISO 4217"):
        Money(Decimal("1.00"), "usd")


def test_arithmetic_and_comparisons() -> None:
    price = Money.of("12.99")
    assert price * 3 == Money.of("38.97")
    assert price + Money.of("0.01") == Money.of("13.00")
    assert Money.zero().is_zero
    assert Money.of("1") < price <= Money.of("12.99") < Money.of("13")
    assert price >= Money.of("12.99") > Money.zero()


def test_rounding_uses_half_up() -> None:
    assert Money.rounded(Decimal("0.125")) == Money.of("0.13")


def test_refuses_to_mix_currencies() -> None:
    with pytest.raises(InvalidValue, match="cannot combine"):
        Money.of("1", "USD") + Money.of("1", "EUR")
