from __future__ import annotations

import re
from dataclasses import dataclass

from ecommerce.domain.errors import InvalidValue

IMAGE_FORMATS = ("avif", "webp")
_KEY = re.compile(r"^[a-z0-9]+(?:[/-][a-z0-9]+)*$")
_PLACEHOLDER_PREFIX = "data:image/"
_MAX_PLACEHOLDER_LENGTH = 4096


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductImage:
    key: str
    width: int
    height: int
    widths: tuple[int, ...]
    formats: tuple[str, ...]
    placeholder: str

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.key):
            raise InvalidValue("image key must be lowercase letters, digits, hyphens and slashes")
        if self.width <= 0 or self.height <= 0:
            raise InvalidValue("image dimensions must be positive")
        if not self.widths or list(self.widths) != sorted(set(self.widths)):
            raise InvalidValue("image widths must be unique and ascending")
        if self.widths[-1] != self.width or self.widths[0] <= 0:
            raise InvalidValue("the largest variant must match the image width")
        if not self.formats or any(fmt not in IMAGE_FORMATS for fmt in self.formats):
            raise InvalidValue(f"image formats must be among {', '.join(IMAGE_FORMATS)}")
        if (
            not self.placeholder.startswith(_PLACEHOLDER_PREFIX)
            or len(self.placeholder) > _MAX_PLACEHOLDER_LENGTH
        ):
            raise InvalidValue("image placeholder must be a small data URI")

    @property
    def content_hash(self) -> str:
        return self.key.rsplit("/", 1)[-1]

    def variant_key(self, width: int, fmt: str) -> str:
        return f"{self.key}-{width}.{fmt}"

    @property
    def variant_keys(self) -> tuple[str, ...]:
        return tuple(self.variant_key(width, fmt) for fmt in self.formats for width in self.widths)

    def height_for(self, width: int) -> int:
        return max(1, round(self.height * width / self.width))
