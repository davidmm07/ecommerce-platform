from __future__ import annotations

import re
from dataclasses import dataclass

from ecommerce.domain.errors import InvalidValue

SKU_MIN_LENGTH = 3
SKU_MAX_LENGTH = 32
_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


@dataclass(frozen=True, slots=True, order=True)
class Sku:
    value: str

    def __post_init__(self) -> None:
        if not SKU_MIN_LENGTH <= len(self.value) <= SKU_MAX_LENGTH:
            raise InvalidValue(f"must be between {SKU_MIN_LENGTH} and {SKU_MAX_LENGTH} characters")
        if not _PATTERN.fullmatch(self.value):
            raise InvalidValue("must contain only letters, digits and single hyphens, e.g. RS-001")

    @classmethod
    def parse(cls, raw: str) -> Sku:
        normalized = raw.strip().upper()
        if not normalized:
            raise InvalidValue("is required")
        return cls(normalized)

    def __str__(self) -> str:
        return self.value
