from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from ecommerce.application.pagination import PageRequest
from ecommerce.domain.catalog.category import Category
from ecommerce.domain.errors import FieldErrors

MAX_SEARCH_TEXT_LENGTH = 100


class ProductSort(StrEnum):
    RELEVANCE = "relevance"
    NAME = "name"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NEWEST = "newest"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductSearchCriteria:
    text: str | None = None
    category: Category | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None
    sort: ProductSort = ProductSort.RELEVANCE
    page: PageRequest = field(default_factory=PageRequest)

    def __post_init__(self) -> None:
        errors = FieldErrors()
        normalized = " ".join(self.text.split()) if self.text else None
        if normalized and len(normalized) > MAX_SEARCH_TEXT_LENGTH:
            errors.add("q", f"must be at most {MAX_SEARCH_TEXT_LENGTH} characters")
        for name, value in (("min_price", self.min_price), ("max_price", self.max_price)):
            if value is not None and (not value.is_finite() or value < 0):
                errors.add(name, "must be a non-negative number")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            errors.add("min_price", "must not be greater than max_price")
        errors.raise_if_any()
        object.__setattr__(self, "text", normalized or None)

    @property
    def effective_sort(self) -> ProductSort:
        if self.sort is ProductSort.RELEVANCE and self.text is None:
            return ProductSort.NAME
        return self.sort
