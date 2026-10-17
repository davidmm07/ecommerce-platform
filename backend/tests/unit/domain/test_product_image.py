from datetime import timedelta

import pytest

from ecommerce.domain.catalog.errors import ProductUnavailable
from ecommerce.domain.catalog.image import ProductImage
from ecommerce.domain.errors import InvalidValue
from tests.factories import NOW, make_product


def image(**overrides: object) -> ProductImage:
    values: dict[str, object] = {
        "key": "products/0b7c-11/5f1e2d",
        "width": 1280,
        "height": 960,
        "widths": (320, 640, 1280),
        "formats": ("avif", "webp"),
        "placeholder": "data:image/webp;base64,AAAA",
    }
    values.update(overrides)
    return ProductImage(**values)


def test_variant_keys_cover_every_width_and_format() -> None:
    product_image = image()
    assert product_image.content_hash == "5f1e2d"
    assert product_image.variant_key(640, "webp") == "products/0b7c-11/5f1e2d-640.webp"
    assert len(product_image.variant_keys) == 6
    assert product_image.height_for(320) == 240


@pytest.mark.parametrize(
    "overrides",
    [
        {"key": "../etc/passwd"},
        {"key": "Products/UPPER"},
        {"width": 0},
        {"widths": (640, 320, 1280)},
        {"widths": (320, 640)},
        {"formats": ("gif",)},
        {"formats": ()},
        {"placeholder": "https://example.com/tiny.webp"},
        {"placeholder": "data:image/webp;base64," + "A" * 5000},
    ],
)
def test_rejects_inconsistent_metadata(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidValue):
        image(**overrides)


def test_products_can_replace_and_remove_their_image() -> None:
    product = make_product()
    later = NOW + timedelta(minutes=1)
    assert product.image is None
    assert product.replace_image(image(), later) is None
    assert product.updated_at == later
    previous = product.replace_image(image(key="products/0b7c-11/aaaa"), later)
    assert previous == image()
    assert product.remove_image(later) == image(key="products/0b7c-11/aaaa")
    assert product.image is None
    assert product.remove_image(later) is None


def test_archived_products_cannot_change_images() -> None:
    product = make_product()
    product.archive(NOW)
    with pytest.raises(ProductUnavailable):
        product.replace_image(image(), NOW)
