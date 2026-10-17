from httpx import AsyncClient

PRODUCTS = "/api/v1/products"


async def test_product_lifecycle(client: AsyncClient, product_payload: dict[str, object]) -> None:
    created = await client.post(PRODUCTS, json=product_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["sku"] == "RS-001"
    assert body["price"] == "89.99"
    assert body["weight_kg"] == "0.350"
    assert body["category_label"] == "Footwear"
    assert created.headers["location"] == f"{PRODUCTS}/{body['id']}"
    assert created.headers["etag"] == '"1"'

    fetched = await client.get(created.headers["location"])
    assert fetched.status_code == 200
    assert fetched.headers["etag"] == '"1"'

    updated = await client.patch(
        created.headers["location"],
        json={"price": 94.99, "stock": 120},
        headers={"If-Match": '"1"'},
    )
    assert updated.status_code == 200
    assert (updated.json()["price"], updated.json()["stock"]) == ("94.99", 120)
    assert updated.headers["etag"] == '"2"'

    deleted = await client.delete(created.headers["location"], headers={"If-Match": 'W/"2"'})
    assert deleted.status_code == 204
    assert (await client.get(created.headers["location"])).status_code == 404


async def test_stale_and_malformed_preconditions(
    client: AsyncClient, product_payload: dict[str, object]
) -> None:
    location = (await client.post(PRODUCTS, json=product_payload)).headers["location"]

    stale = await client.patch(location, json={"stock": 1}, headers={"If-Match": '"9"'})
    assert stale.status_code == 412
    assert stale.json()["current_version"] == 1

    malformed = await client.delete(location, headers={"If-Match": "abc"})
    assert malformed.status_code == 400
    assert malformed.headers["content-type"] == "application/problem+json"


async def test_duplicate_skus_conflict(
    client: AsyncClient, product_payload: dict[str, object]
) -> None:
    await client.post(PRODUCTS, json=product_payload)
    conflict = await client.post(PRODUCTS, json=product_payload | {"sku": " RS-001 "})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "duplicate_sku"


async def test_edge_validation_returns_field_errors(
    client: AsyncClient, product_payload: dict[str, object]
) -> None:
    response = await client.post(
        PRODUCTS,
        json=product_payload | {"price": "1.999", "category": "spaceships", "unknown": True},
    )
    assert response.status_code == 422
    problem = response.json()
    assert problem["code"] == "validation_failed"
    assert {error["field"] for error in problem["errors"]} == {"price", "category", "unknown"}


async def test_domain_validation_returns_field_errors(
    client: AsyncClient, product_payload: dict[str, object]
) -> None:
    response = await client.post(
        PRODUCTS, json=product_payload | {"name": "<b>Bold</b>", "description": "bad\u0000byte"}
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "name", "message": "must be plain text without HTML markup"},
        {"field": "description", "message": "must not contain control characters"},
    ]


async def test_partial_updates_validate_through_the_domain(
    client: AsyncClient, product_payload: dict[str, object]
) -> None:
    location = (await client.post(PRODUCTS, json=product_payload)).headers["location"]
    response = await client.patch(location, json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "name", "message": "is required"}]


async def test_search_endpoint(client: AsyncClient, product_payload: dict[str, object]) -> None:
    await client.post(PRODUCTS, json=product_payload)
    await client.post(
        PRODUCTS,
        json=product_payload
        | {
            "sku": "BS-021",
            "name": "Bluetooth Speaker",
            "category": "electronics",
            "price": "59.99",
        },
    )
    found = await client.get(PRODUCTS, params={"q": "speaker", "page_size": 5, "ignored": "x"})
    assert found.status_code == 200
    page = found.json()
    assert [item["sku"] for item in page["items"]] == ["BS-021"]
    assert {key: page[key] for key in ("page", "page_size", "total", "total_pages")} == {
        "page": 1,
        "page_size": 5,
        "total": 1,
        "total_pages": 1,
    }

    filtered = await client.get(PRODUCTS, params={"category": "footwear", "sort": "price_desc"})
    assert [item["sku"] for item in filtered.json()["items"]] == ["RS-001"]

    invalid = await client.get(PRODUCTS, params={"page_size": 500, "sort": "random"})
    assert invalid.status_code == 422
    assert {error["field"] for error in invalid.json()["errors"]} == {"page_size", "sort"}


async def test_categories_are_listed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/categories")
    categories = response.json()
    assert {"value": "home-office", "label": "Home & Office"} in categories
    assert len(categories) == 18


async def test_unknown_ids_are_not_found(client: AsyncClient) -> None:
    missing = await client.get(f"{PRODUCTS}/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    malformed = await client.get(f"{PRODUCTS}/not-a-uuid")
    assert malformed.status_code == 422
