from httpx import AsyncClient

from tests.conftest import SAMPLE_CSV

IMPORTS = "/api/v1/product-imports"


async def test_imports_the_sample_file(client: AsyncClient) -> None:
    files = {"file": ("products.csv", SAMPLE_CSV.read_bytes(), "text/csv")}
    response = await client.post(IMPORTS, files=files)

    assert response.status_code == 200
    report = response.json()
    assert report["dry_run"] is False
    assert report["summary"] == {
        "total_rows": 97,
        "created": 83,
        "updated": 0,
        "unchanged": 0,
        "skipped": 5,
        "failed": 9,
    }
    failed = {row["sku"]: row["messages"] for row in report["rows"] if row["outcome"] == "failed"}
    assert failed["YM-015"] == ["price: 'free' is not a valid decimal number"]
    assert (await client.get("/api/v1/products", params={"page_size": 1})).json()["total"] == 83


async def test_dry_run_does_not_persist(client: AsyncClient) -> None:
    files = {"file": ("products.csv", SAMPLE_CSV.read_bytes(), "text/csv")}
    response = await client.post(IMPORTS, params={"dry_run": "true"}, files=files)
    assert response.json()["dry_run"] is True
    assert (await client.get("/api/v1/products")).json()["total"] == 0


async def test_rejects_files_that_are_not_csv(client: AsyncClient) -> None:
    files = {"file": ("photo.png", b"\x89PNG", "image/png")}
    response = await client.post(IMPORTS, files=files)
    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


async def test_rejects_files_without_the_required_columns(client: AsyncClient) -> None:
    files = {"file": ("products.csv", b"title,cost\nA,1\n", "text/csv")}
    response = await client.post(IMPORTS, files=files)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_import_file"


async def test_rejects_files_over_the_size_limit(client: AsyncClient) -> None:
    oversized = b"name,sku,description,category,price,stock,weight_kg\n" + b"x" * 70_000
    response = await client.post(IMPORTS, files={"file": ("big.csv", oversized, "text/csv")})
    assert response.status_code == 413


async def test_rejects_request_bodies_over_the_global_limit(client: AsyncClient) -> None:
    response = await client.post(IMPORTS, files={"file": ("huge.csv", b"x" * 200_000, "text/csv")})
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


async def test_requires_a_file(client: AsyncClient) -> None:
    response = await client.post(IMPORTS)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "file"
