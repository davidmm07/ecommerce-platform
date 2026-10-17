import pytest
from httpx import AsyncClient

from ecommerce.container import Container


async def test_health_probes(client: AsyncClient) -> None:
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    assert (await client.get("/health/ready")).json() == {"status": "ok", "database": "up"}


async def test_readiness_reports_a_down_database(
    client: AsyncClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down() -> bool:
        return False

    monkeypatch.setattr(container, "database_is_ready", down)
    response = await client.get("/health/ready")
    assert response.status_code == 503


async def test_request_ids_are_propagated_or_generated(client: AsyncClient) -> None:
    echoed = await client.get("/health/live", headers={"X-Request-ID": "trace-12345678"})
    assert echoed.headers["x-request-id"] == "trace-12345678"
    generated = await client.get("/health/live", headers={"X-Request-ID": "bad id!"})
    assert len(generated.headers["x-request-id"]) == 32


async def test_security_headers_are_set(client: AsyncClient) -> None:
    headers = (await client.get("/health/live")).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"


async def test_unknown_routes_and_methods_use_problem_details(client: AsyncClient) -> None:
    missing = await client.get("/api/v1/nope")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"
    assert missing.json()["code"] == "not_found"
    assert missing.json()["request_id"] == missing.headers["x-request-id"]
    not_allowed = await client.put("/api/v1/products")
    assert not_allowed.status_code == 405


async def test_unexpected_errors_hide_internals(
    client: AsyncClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def explode(*_: object) -> None:
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(container.get_product, "execute", explode)
    response = await client.get("/api/v1/products/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.json()["code"] == "internal_error"
    assert response.headers["x-request-id"] == response.json()["request_id"]


async def test_cors_preflight_allows_the_frontend(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/products",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "If-Match",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_openapi_document_is_served(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    assert "place_order" in {
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    }
