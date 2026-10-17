from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import TYPE_CHECKING, Protocol

from ecommerce.domain.errors import InvalidValue
from ecommerce.domain.money import Money

if TYPE_CHECKING:
    from ecommerce.domain.ordering.order import OrderLine


class ShippingPolicy(Protocol):
    def cost_for(self, subtotal: Money, total_weight_kg: Decimal) -> Money: ...


@dataclass(frozen=True, slots=True)
class WeightBasedShipping:
    base_fee: Money
    per_kg_fee: Money

    def cost_for(self, subtotal: Money, total_weight_kg: Decimal) -> Money:
        if total_weight_kg <= 0:
            return Money.zero(subtotal.currency)
        billable_kg = int(total_weight_kg.to_integral_value(rounding=ROUND_CEILING))
        return self.base_fee + self.per_kg_fee * billable_kg


@dataclass(frozen=True, slots=True)
class FreeShippingOverThreshold:
    inner: ShippingPolicy
    threshold: Money

    def cost_for(self, subtotal: Money, total_weight_kg: Decimal) -> Money:
        if subtotal >= self.threshold:
            return Money.zero(subtotal.currency)
        return self.inner.cost_for(subtotal, total_weight_kg)


@dataclass(frozen=True, slots=True)
class OrderTotals:
    subtotal: Money
    shipping: Money
    total: Money
    total_weight_kg: Decimal


def calculate_totals(lines: Sequence[OrderLine], shipping_policy: ShippingPolicy) -> OrderTotals:
    if not lines:
        raise InvalidValue("an order needs at least one line")
    currency = lines[0].unit_price.currency
    subtotal = Money.zero(currency)
    weight = Decimal("0.000")
    for line in lines:
        subtotal += line.line_total
        weight += line.line_weight_kg
    shipping = shipping_policy.cost_for(subtotal, weight)
    return OrderTotals(
        subtotal=subtotal, shipping=shipping, total=subtotal + shipping, total_weight_kg=weight
    )
