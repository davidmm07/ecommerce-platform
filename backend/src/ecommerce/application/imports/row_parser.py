import re
from dataclasses import dataclass
from decimal import Decimal

from ecommerce.application.catalog.images import ImageCreditInput, ImageSource
from ecommerce.application.imports.table import RawProductRow
from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.image import ImageCredit, parse_web_url
from ecommerce.domain.catalog.product import (
    ProductDetails,
    check_price,
    check_stock,
    check_weight,
    clean_description,
    clean_name,
)
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import DomainValidationError, FieldErrors, InvalidValue

REQUIRED_COLUMNS = ("name", "sku", "description", "category", "price", "stock", "weight_kg")
IMAGE_COLUMNS = (
    "image_url",
    "image_author",
    "image_license",
    "image_license_url",
    "image_source_url",
)
_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_ECHO_LIMIT = 40


@dataclass(frozen=True, slots=True)
class ProductDraft:
    line: int
    sku: Sku
    details: ProductDetails
    notes: tuple[str, ...] = ()
    image: ImageSource | None = None

    def same_content(self, other: "ProductDraft") -> bool:
        return self.details == other.details and self.image == other.image


def parse_product_row(row: RawProductRow) -> ProductDraft:
    errors = FieldErrors()
    notes: list[str] = []
    with errors.collect("sku"):
        sku = Sku.parse(row.get("sku"))
    with errors.collect("name"):
        name = clean_name(row.get("name"))
    with errors.collect("description"):
        description = clean_description(row.get("description"))
    with errors.collect("category"):
        category = Category.parse(row.get("category"))
    with errors.collect("price"):
        raw_price = row.get("price").strip()
        if raw_price.startswith("$"):
            notes.append(f"price: currency symbol removed from '{raw_price}'")
            raw_price = raw_price[1:]
        price = check_price(parse_decimal(raw_price))
    with errors.collect("stock"):
        stock = check_stock(parse_integer(row.get("stock")))
    with errors.collect("weight_kg"):
        weight_kg = check_weight(parse_decimal(row.get("weight_kg")))
    image = _parse_image(row, errors)
    errors.raise_if_any()
    details = ProductDetails(
        name=name,
        description=description,
        category=category,
        price=price,
        stock=stock,
        weight_kg=weight_kg,
    )
    return ProductDraft(
        line=row.line,
        sku=sku,
        details=details,
        notes=tuple(notes),
        image=ImageSource(sku.value, image[0], image[1]) if image else None,
    )


def _parse_image(
    row: RawProductRow, errors: FieldErrors
) -> tuple[str, ImageCreditInput | None] | None:
    url = row.get("image_url").strip()
    credit = ImageCreditInput(
        author=row.get("image_author").strip(),
        license=row.get("image_license").strip(),
        source_url=row.get("image_source_url").strip(),
        license_url=row.get("image_license_url").strip() or None,
    )
    has_credit = any((credit.author, credit.license, credit.source_url, credit.license_url))
    if not url:
        if has_credit:
            errors.add("image_url", "is required when a photo credit is given")
        return None
    with errors.collect("image_url"):
        parse_web_url(url)
    if not has_credit:
        return url, None
    try:
        ImageCredit.build(
            author=credit.author,
            license=credit.license,
            source_url=credit.source_url,
            license_url=credit.license_url,
        )
    except DomainValidationError as exc:
        for error in exc.errors:
            errors.add(f"image_{error.field}", error.message)
    return url, credit


def parse_decimal(raw: str) -> Decimal:
    text = raw.strip()
    if not text:
        raise InvalidValue("is required")
    if not _DECIMAL.fullmatch(text):
        raise InvalidValue(f"'{_echo(text)}' is not a valid decimal number")
    return Decimal(text)


def parse_integer(raw: str) -> int:
    text = raw.strip()
    if not text:
        raise InvalidValue("is required")
    if not _INTEGER.fullmatch(text):
        raise InvalidValue(f"'{_echo(text)}' is not a whole number")
    return int(text)


def _echo(text: str) -> str:
    return text if len(text) <= _ECHO_LIMIT else text[: _ECHO_LIMIT - 3] + "..."
