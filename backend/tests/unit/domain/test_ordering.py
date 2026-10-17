from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ecommerce.domain.errors import DomainValidationError, InvalidValue
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.errors import InvalidOrderTransition
from ecommerce.domain.ordering.order import (
    Customer,
    Order,
    OrderLine,
    OrderStatus,
    PaymentSummary,
    ShippingAddress,
    order_number_for,
)
from ecommerce.domain.ordering.pricing import (
    FreeShippingOverThreshold,
    WeightBasedShipping,
    calculate_totals,
)
from ecommerce.domain.payments.card import CardBrand, PaymentCard, brand_of, passes_luhn
from tests.factories import NOW

SHIPPING = FreeShippingOverThreshold(
    inner=WeightBasedShipping(base_fee=Money.of("4.99"), per_kg_fee=Money.of("1.25")),
    threshold=Money.of("100.00"),
)


def line(price: str = "10.00", quantity: int = 1, weight: str = "0.500") -> OrderLine:
    return OrderLine(
        product_id=uuid4(),
        sku="RS-001",
        name="Running Shoes",
        unit_price=Money.of(price),
        quantity=quantity,
        unit_weight_kg=Decimal(weight),
    )


def place(*lines: OrderLine) -> Order:
    return Order.place(
        order_id=UUID("00000000-0000-4000-8000-000000000001"),
        customer=Customer.build(name="Ada", email="ada@example.com"),
        shipping_address=ShippingAddress.build(
            line1="1 Main St", city="Springfield", postal_code="12345", country="us"
        ),
        lines=lines,
        shipping_policy=SHIPPING,
        idempotency_key="key-00000001",
        request_fingerprint="f" * 64,
        now=NOW,
    )


class TestShipping:
    def test_charges_base_fee_plus_each_started_kilogram(self) -> None:
        totals = calculate_totals([line("20.00", 2, "1.200")], SHIPPING)
        assert totals.subtotal == Money.of("40.00")
        assert totals.total_weight_kg == Decimal("2.400")
        assert totals.shipping == Money.of("8.74")
        assert totals.total == Money.of("48.74")

    def test_is_free_above_the_threshold(self) -> None:
        totals = calculate_totals([line("100.00", 1, "35.000")], SHIPPING)
        assert totals.shipping.is_zero

    def test_weightless_goods_ship_for_free(self) -> None:
        totals = calculate_totals([line("25.00", 1, "0")], SHIPPING)
        assert totals.shipping.is_zero

    def test_requires_lines(self) -> None:
        with pytest.raises(InvalidValue):
            calculate_totals([], SHIPPING)


class TestOrder:
    def test_place_snapshots_lines_and_totals(self) -> None:
        order = place(line("10.00", 2), line("5.00", 1))
        assert order.status is OrderStatus.PENDING_PAYMENT
        assert order.item_count == 3
        assert order.totals.subtotal == Money.of("25.00")
        assert order.number == "ORD-000000000001"
        assert order.shipping_address.country == "US"

    def test_payment_moves_the_order_once(self) -> None:
        order = place(line())
        order.mark_paid(PaymentSummary(card_brand="visa", card_last4="4242"), NOW)
        assert order.status is OrderStatus.PAID
        with pytest.raises(InvalidOrderTransition):
            order.mark_payment_failed(PaymentSummary(card_brand="visa", card_last4="4242"), NOW)

    def test_rejects_duplicate_products_and_empty_orders(self) -> None:
        duplicated = line()
        with pytest.raises(InvalidValue, match="only once"):
            place(duplicated, duplicated)
        with pytest.raises(InvalidValue, match="at least one line"):
            place()

    @pytest.mark.parametrize("quantity", [0, 101])
    def test_line_quantity_limits(self, quantity: int) -> None:
        with pytest.raises(InvalidValue):
            line(quantity=quantity)

    def test_order_numbers_are_stable_per_id(self) -> None:
        order_id = uuid4()
        assert order_number_for(order_id) == order_number_for(order_id)
        assert len(order_number_for(order_id)) == 16


class TestCustomerAndAddress:
    def test_normalizes_contact_details(self) -> None:
        customer = Customer.build(name=" Ada  Lovelace ", email=" Ada@Example.COM ")
        assert customer == Customer(name="Ada Lovelace", email="ada@example.com")

    def test_collects_all_address_errors(self) -> None:
        with pytest.raises(DomainValidationError) as caught:
            ShippingAddress.build(line1="", city=" ", postal_code="!", country="USA")
        assert {error.field for error in caught.value.errors} == {
            "line1",
            "city",
            "postal_code",
            "country",
        }

    @pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "a b@c.com"])
    def test_rejects_invalid_emails(self, email: str) -> None:
        with pytest.raises(DomainValidationError):
            Customer.build(name="Ada", email=email)


class TestPaymentCard:
    def test_parses_and_masks_the_number(self) -> None:
        card = PaymentCard.parse(
            number="4242 4242-4242 4242",
            expiry_month=12,
            expiry_year=2030,
            cvc="123",
            holder_name="Ada",
        )
        assert card.last4 == "4242"
        assert card.brand is CardBrand.VISA
        assert "4242424242424242" not in repr(card)
        assert "123" not in repr(card)

    def test_reports_every_invalid_field(self) -> None:
        with pytest.raises(DomainValidationError) as caught:
            PaymentCard.parse(
                number="4242424242424241",
                expiry_month=13,
                expiry_year=99,
                cvc="12a",
                holder_name="",
            )
        assert {error.field for error in caught.value.errors} == {
            "card_number",
            "expiry_month",
            "expiry_year",
            "cvc",
            "holder_name",
        }

    @pytest.mark.parametrize(
        ("number", "brand"),
        [
            ("5555555555554444", CardBrand.MASTERCARD),
            ("2223003122003222", CardBrand.MASTERCARD),
            ("378282246310005", CardBrand.AMEX),
            ("6011111111111117", CardBrand.DISCOVER),
            ("3530111333300000", CardBrand.UNKNOWN),
        ],
    )
    def test_detects_brands(self, number: str, brand: CardBrand) -> None:
        assert passes_luhn(number)
        assert brand_of(number) is brand

    def test_expiry_is_inclusive_of_the_current_month(self) -> None:
        card = PaymentCard.parse(
            number="4242424242424242", expiry_month=10, expiry_year=2026, cvc="123", holder_name="A"
        )
        assert not card.is_expired(date(2026, 10, 31))
        assert card.is_expired(date(2026, 11, 1))

    @pytest.mark.parametrize("number", ["", "4242", "42424242424242424242", chr(0x0664) * 16])
    def test_rejects_wrong_lengths_and_non_ascii_digits(self, number: str) -> None:
        with pytest.raises(DomainValidationError):
            PaymentCard.parse(
                number=number, expiry_month=1, expiry_year=2030, cvc="123", holder_name="A"
            )
