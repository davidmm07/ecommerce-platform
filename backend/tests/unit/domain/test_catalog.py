from datetime import timedelta
from decimal import Decimal

import pytest

from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.errors import InsufficientStock, ProductUnavailable
from ecommerce.domain.catalog.product import ProductDetails
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import DomainValidationError, InvalidValue
from tests.factories import NOW, make_product, product_details


class TestSku:
    def test_normalizes_case_and_whitespace(self) -> None:
        assert Sku.parse("  rs-001 ") == Sku("RS-001")

    @pytest.mark.parametrize(
        "raw", ["", "  ", "AB", "RS 001", "RS--001", "-RS1", "R" * 33, chr(0xC9) + "T-1"]
    )
    def test_rejects_malformed_values(self, raw: str) -> None:
        with pytest.raises(InvalidValue):
            Sku.parse(raw)


class TestCategory:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Home & Office", Category.HOME_AND_OFFICE),
            ("home-office", Category.HOME_AND_OFFICE),
            ("FOOD AND BEVERAGE", Category.FOOD_AND_BEVERAGE),
            (" electronics ", Category.ELECTRONICS),
        ],
    )
    def test_accepts_labels_and_slugs(self, raw: str, expected: Category) -> None:
        assert Category.parse(raw) is expected

    def test_exposes_human_labels(self) -> None:
        assert Category.FOOD_AND_BEVERAGE.label == "Food & Beverage"

    def test_rejects_missing_and_unknown_values(self) -> None:
        with pytest.raises(InvalidValue, match="required"):
            Category.parse("  ")
        with pytest.raises(InvalidValue, match="not a known category"):
            Category.parse("Spaceships")


class TestProductDetails:
    def build(self, **overrides: object) -> ProductDetails:
        values: dict[str, object] = {
            "name": "  Running   Shoes ",
            "description": " Lightweight ",
            "category": "Footwear",
            "price": Decimal("89.99"),
            "stock": 150,
            "weight_kg": Decimal("0.35"),
        }
        values.update(overrides)
        return ProductDetails.build(**values)

    def test_normalizes_text_and_numbers(self) -> None:
        details = self.build()
        assert details.name == "Running Shoes"
        assert details.description == "Lightweight"
        assert details.category is Category.FOOTWEAR
        assert details.weight_kg == Decimal("0.350")

    def test_reports_every_invalid_field_at_once(self) -> None:
        with pytest.raises(DomainValidationError) as caught:
            self.build(
                name="<script>alert('xss')</script>",
                category="",
                price=Decimal("0"),
                stock=-5,
                weight_kg=Decimal("1.2345"),
            )
        fields = {error.field: error.message for error in caught.value.errors}
        assert fields == {
            "name": "must be plain text without HTML markup",
            "category": "is required",
            "price": "must be greater than 0",
            "stock": "must not be negative",
            "weight_kg": "must have at most 3 decimal places",
        }

    @pytest.mark.parametrize(
        ("overrides", "field"),
        [
            ({"name": "   "}, "name"),
            ({"name": "x" * 201}, "name"),
            ({"description": "bad\x00byte"}, "description"),
            ({"price": Decimal("1000000.01")}, "price"),
            ({"price": Decimal("1.999")}, "price"),
            ({"stock": 1_000_001}, "stock"),
            ({"weight_kg": Decimal("-1")}, "weight_kg"),
            ({"weight_kg": Decimal("1000.001")}, "weight_kg"),
            ({"weight_kg": Decimal("NaN")}, "weight_kg"),
        ],
    )
    def test_enforces_limits(self, overrides: dict[str, object], field: str) -> None:
        with pytest.raises(DomainValidationError) as caught:
            self.build(**overrides)
        assert [error.field for error in caught.value.errors] == [field]

    def test_keeps_plain_text_that_only_looks_suspicious(self) -> None:
        details = self.build(name="Robert'); DROP TABLE products;--", description="Size < 5 > 3")
        assert details.name == "Robert'); DROP TABLE products;--"


class TestProduct:
    def test_reserve_and_release_adjust_stock(self) -> None:
        product = make_product(stock=3)
        later = NOW + timedelta(minutes=1)
        product.reserve(2, later)
        assert product.stock == 1
        assert product.updated_at == later
        product.release(2, later)
        assert product.stock == 3

    def test_reserving_more_than_available_reports_the_shortage(self) -> None:
        product = make_product(stock=1)
        with pytest.raises(InsufficientStock) as caught:
            product.reserve(2, NOW)
        assert caught.value.details() == {
            "shortages": [{"sku": "RS-001", "requested": 2, "available": 1}]
        }

    @pytest.mark.parametrize("quantity", [0, -1])
    def test_quantities_must_be_positive(self, quantity: int) -> None:
        with pytest.raises(InvalidValue):
            make_product().reserve(quantity, NOW)

    def test_revise_reports_whether_anything_changed(self) -> None:
        product = make_product()
        assert product.revise(product.details, NOW) is False
        assert product.revise(product_details(price="94.99"), NOW + timedelta(seconds=1)) is True
        assert str(product.price) == "94.99 USD"

    def test_archived_products_cannot_be_sold_or_changed(self) -> None:
        product = make_product()
        product.archive(NOW)
        product.archive(NOW + timedelta(days=1))
        assert product.archived_at == NOW
        with pytest.raises(ProductUnavailable):
            product.reserve(1, NOW)
        with pytest.raises(ProductUnavailable):
            product.revise(product_details(name="Other"), NOW)
        assert product.is_archived
