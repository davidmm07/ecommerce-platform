from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from ecommerce.domain.errors import FieldErrors, InvalidValue
from ecommerce.domain.text import single_line

IMAGE_FORMATS = ("avif", "webp")
MAX_URL_LENGTH = 2048
_KEY = re.compile(r"^[a-z0-9]+(?:[/-][a-z0-9]+)*$")
_PLACEHOLDER_PREFIX = "data:image/"
_MAX_PLACEHOLDER_LENGTH = 4096


def parse_web_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise InvalidValue("is required")
    if len(url) > MAX_URL_LENGTH or any(char.isspace() for char in url):
        raise InvalidValue(f"must be a URL of at most {MAX_URL_LENGTH} characters without spaces")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise InvalidValue("must be an http or https URL")
    if parts.username or parts.password:
        raise InvalidValue("must not contain credentials")
    return url


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageCredit:
    author: str
    license: str
    source_url: str
    license_url: str | None = None

    @classmethod
    def build(
        cls, *, author: str, license: str, source_url: str, license_url: str | None = None
    ) -> ImageCredit:
        errors = FieldErrors()
        with errors.collect("author"):
            clean_author = single_line(author, max_length=200)
        with errors.collect("license"):
            clean_license = single_line(license, max_length=60)
        with errors.collect("source_url"):
            clean_source = parse_web_url(source_url)
        with errors.collect("license_url"):
            clean_license_url = parse_web_url(license_url) if license_url else None
        errors.raise_if_any()
        return cls(
            author=clean_author,
            license=clean_license,
            source_url=clean_source,
            license_url=clean_license_url,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductImage:
    key: str
    width: int
    height: int
    widths: tuple[int, ...]
    formats: tuple[str, ...]
    placeholder: str
    origin_url: str | None = None
    credit: ImageCredit | None = None

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
        if self.origin_url is not None:
            parse_web_url(self.origin_url)

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
