from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.images import jpeg_bytes, png_bytes

PRODUCTS = "/api/v1/products"


@pytest.fixture
async def product(client: AsyncClient, product_payload: dict[str, object]) -> dict[str, object]:
    response = await client.post(PRODUCTS, json=product_payload)
    return dict(response.json())


def upload(content: bytes, name: str = "photo.jpg", content_type: str = "image/jpeg") -> dict:
    return {"file": (name, content, content_type)}


async def test_upload_returns_responsive_sources(
    client: AsyncClient, product: dict[str, object], media_root: Path
) -> None:
    response = await client.put(
        f"{PRODUCTS}/{product['id']}/image",
        files=upload(jpeg_bytes(1600, 1200)),
        headers={"If-Match": '"1"'},
    )

    assert response.status_code == 200
    assert response.headers["etag"] == '"2"'
    image = response.json()["image"]
    assert (image["width"], image["height"]) == (1280, 960)
    assert image["placeholder"].startswith("data:image/webp;base64,")
    assert image["url"].startswith(f"/media/products/{product['id']}/")
    assert image["url"].endswith("-640.webp")
    assert [source["type"] for source in image["sources"]] == ["image/avif", "image/webp"]
    assert image["sources"][0]["srcset"].count(" 160w") == 1
    assert image["sources"][0]["srcset"].endswith("-1280.avif 1280w")

    stored = sorted(path.name for path in (media_root / "products" / str(product["id"])).iterdir())
    assert len(stored) == 10

    served = await client.get(image["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"

    fetched = await client.get(f"{PRODUCTS}/{product['id']}")
    assert fetched.json()["image"] == image
    listed = await client.get(PRODUCTS)
    assert listed.json()["items"][0]["image"] == image


async def test_replace_and_remove_clean_up_the_files(
    client: AsyncClient, product: dict[str, object], media_root: Path
) -> None:
    url = f"{PRODUCTS}/{product['id']}/image"
    await client.put(url, files=upload(jpeg_bytes(800, 600)))
    replaced = await client.put(url, files=upload(png_bytes(), "logo.png", "image/png"))
    folder = media_root / "products" / str(product["id"])
    names = {path.name for path in folder.iterdir()}
    current = replaced.json()["image"]["url"].rsplit("/", 1)[-1].split("-")[0]
    assert all(name.startswith(current) for name in names)

    removed = await client.delete(url)
    assert removed.status_code == 200
    assert removed.json()["image"] is None
    assert not folder.exists()


@pytest.mark.parametrize(
    ("files", "status", "code"),
    [
        (upload(b"%PDF-1.7", "doc.pdf", "application/pdf"), 415, "unsupported_media_type"),
        (upload(b"<svg></svg>", "x.svg", "image/svg+xml"), 415, "unsupported_image_type"),
        (upload(b"not really a jpeg"), 415, "unsupported_image_type"),
        (upload(jpeg_bytes(120, 120)), 422, "invalid_image"),
        (upload(b""), 422, "invalid_image"),
    ],
)
async def test_rejects_invalid_uploads(
    client: AsyncClient,
    product: dict[str, object],
    files: dict,
    status: int,
    code: str,
) -> None:
    response = await client.put(f"{PRODUCTS}/{product['id']}/image", files=files)
    assert response.status_code == status
    assert response.json()["code"] == code


async def test_rejects_files_over_the_image_limit(
    client: AsyncClient, product: dict[str, object]
) -> None:
    oversized = b"\xff\xd8" + b"0" * (2 * 1024 * 1024 + 10)
    response = await client.put(f"{PRODUCTS}/{product['id']}/image", files=upload(oversized))
    assert response.status_code == 413
    assert response.json()["code"] == "image_too_large"


async def test_respects_preconditions_and_missing_products(
    client: AsyncClient, product: dict[str, object]
) -> None:
    stale = await client.put(
        f"{PRODUCTS}/{product['id']}/image",
        files=upload(jpeg_bytes(400, 400)),
        headers={"If-Match": '"7"'},
    )
    assert stale.status_code == 412
    missing = await client.put(
        f"{PRODUCTS}/00000000-0000-4000-8000-000000000000/image",
        files=upload(jpeg_bytes(400, 400)),
    )
    assert missing.status_code == 404


async def test_products_without_images_report_null(
    client: AsyncClient, product: dict[str, object]
) -> None:
    assert product["image"] is None
    removed = await client.delete(f"{PRODUCTS}/{product['id']}/image")
    assert removed.status_code == 200
    assert removed.headers["etag"] == '"1"'


async def test_import_from_url_processes_and_credits_the_image(
    client: AsyncClient, product: dict[str, object]
) -> None:
    response = await client.put(
        f"{PRODUCTS}/{product['id']}/image/from-url",
        json={
            "url": "https://images.example.com/lamp.jpg",
            "credit": {
                "author": "Jane Doe",
                "license": "CC BY 2.0",
                "source_url": "https://www.flickr.com/photos/example/1",
                "license_url": "https://creativecommons.org/licenses/by/2.0/",
            },
        },
        headers={"If-Match": '"1"'},
    )

    assert response.status_code == 200
    image = response.json()["image"]
    assert (image["width"], image["height"]) == (900, 600)
    assert image["url"].startswith("/media/")
    assert image["credit"]["author"] == "Jane Doe"
    served = await client.get(image["url"])
    assert served.status_code == 200


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"url": "https://images.example.com/missing.jpg"}, 502, "image_source_unavailable"),
        ({"url": "file:///etc/passwd"}, 422, "validation_failed"),
        (
            {"url": "https://images.example.com/lamp.jpg", "credit": {"author": "x"}},
            422,
            "validation_failed",
        ),
    ],
)
async def test_import_from_url_reports_problems(
    client: AsyncClient, product: dict[str, object], body: dict, status: int, code: str
) -> None:
    response = await client.put(f"{PRODUCTS}/{product['id']}/image/from-url", json=body)
    assert response.status_code == status
    assert response.json()["code"] == code
