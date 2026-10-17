import math
from collections.abc import Sequence
from dataclasses import dataclass

from ecommerce.domain.errors import FieldErrors

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_PAGE_NUMBER = 10_000


@dataclass(frozen=True, slots=True)
class PageRequest:
    number: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        errors = FieldErrors()
        if not 1 <= self.number <= MAX_PAGE_NUMBER:
            errors.add("page", f"must be between 1 and {MAX_PAGE_NUMBER}")
        if not 1 <= self.size <= MAX_PAGE_SIZE:
            errors.add("page_size", f"must be between 1 and {MAX_PAGE_SIZE}")
        errors.raise_if_any()

    @property
    def offset(self) -> int:
        return (self.number - 1) * self.size


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: Sequence[T]
    total: int
    request: PageRequest

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.request.size)
