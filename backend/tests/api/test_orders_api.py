import pytest
from httpx import AsyncClient

ORDERS = "/api/v1/orders"


@pytest.fixture
async def product_id(client: AsyncClient, product_payload: dict[str, object]) -> str:
    response = await client.post("/api/v1/products", json=product_payload | {"stock": 3})
    return str(response.json()["id"])


def order_body(product_id: str, *, quantity: int = 1, card: str = "4242 4242 4242 4242") -> dict:
    return {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "customer": {"name": "Ada Lovelace", "email": "Ada@Example.com"},
        "shipping_address": {
            "line1": "221B Baker Street",
            "city": "London",
            "postal_code": "NW1 6XE",
            "country": "gb",
        },
        "payment": {
            "card_number": card,
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvc": "123",
            "holder_name": "Ada Lovelace",
        },
    }


async def test_quote_prices_the_cart(client: AsyncClient, product_id: str) -> None:
    response = await client.post(
        "/api/v1/checkout/quote", json={"items": [{"product_id": product_id, "quantity": 2}]}
    )
    assert response.status_code == 200
    assert response.json()["totals"] == {
        "subtotal": "179.98",
        "shipping": "0.00",
        "total": "179.98",
        "total_weight_kg": "0.700",
        "currency": "USD",
    }


async def test_checkout_and_idempotent_replay(client: AsyncClient, product_id: str) -> None:
    headers = {"Idempotency-Key": "api-checkout-0001"}
    created = await client.post(ORDERS, json=order_body(product_id), headers=headers)

    assert created.status_code == 201
    order = created.json()
    assert order["status"] == "paid"
    assert order["customer"]["email"] == "ada@example.com"
    assert order["payment"]["card_last4"] == "4242"
    assert created.headers["location"] == f"{ORDERS}/{order['id']}"

    replay = await client.post(ORDERS, json=order_body(product_id), headers=headers)
    assert replay.status_code == 200
    assert replay.headers["idempotent-replayed"] == "true"
    assert replay.json()["id"] == order["id"]

    fetched = await client.get(created.headers["location"])
    assert fetched.json()["number"] == order["number"]
    product = await client.get(f"/api/v1/products/{product_id}")
    assert product.json()["stock"] == 2


async def test_declined_cards_answer_payment_required(client: AsyncClient, product_id: str) -> None:
    response = await client.post(
        ORDERS,
        json=order_body(product_id, card="4000 0000 0000 9995"),
        headers={"Idempotency-Key": "api-declined-0001"},
    )
    assert response.status_code == 402
    problem = response.json()
    assert problem["decline_code"] == "insufficient_funds"
    failed = await client.get(f"{ORDERS}/{problem['order_id']}")
    assert failed.json()["status"] == "payment_failed"
    assert (await client.get(f"/api/v1/products/{product_id}")).json()["stock"] == 3


async def test_provider_outages_answer_bad_gateway(client: AsyncClient, product_id: str) -> None:
    response = await client.post(
        ORDERS,
        json=order_body(product_id, card="4000 0000 0000 0119"),
        headers={"Idempotency-Key": "api-outage-0001"},
    )
    assert response.status_code == 502
    assert response.json()["code"] == "payment_unavailable"


async def test_insufficient_stock_lists_the_shortages(client: AsyncClient, product_id: str) -> None:
    response = await client.post(
        ORDERS,
        json=order_body(product_id, quantity=5),
        headers={"Idempotency-Key": "api-short-0001"},
    )
    assert response.status_code == 409
    assert response.json()["shortages"] == [{"sku": "RS-001", "requested": 5, "available": 3}]


async def test_reusing_a_key_for_another_body_is_unprocessable(
    client: AsyncClient, product_id: str
) -> None:
    headers = {"Idempotency-Key": "api-reuse-0001"}
    await client.post(ORDERS, json=order_body(product_id), headers=headers)
    response = await client.post(ORDERS, json=order_body(product_id, quantity=2), headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_reused"


async def test_validation_never_echoes_card_data(client: AsyncClient, product_id: str) -> None:
    body = order_body(product_id, card="4242424242424241")
    body["payment"]["cvc"] = "12"
    response = await client.post(ORDERS, json=body, headers={"Idempotency-Key": "api-card-0001"})
    assert response.status_code == 422
    assert "4242424242424241" not in response.text
    assert {error["field"] for error in response.json()["errors"]} == {"payment.cvc"}

    body["payment"]["cvc"] = "123"
    response = await client.post(ORDERS, json=body, headers={"Idempotency-Key": "api-card-0002"})
    assert response.json()["errors"] == [
        {"field": "payment.card_number", "message": "is not a valid card number"}
    ]
    assert "4242424242424241" not in response.text


async def test_requires_an_idempotency_key(client: AsyncClient, product_id: str) -> None:
    response = await client.post(ORDERS, json=order_body(product_id))
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "header.Idempotency-Key"


async def test_lists_orders_newest_first(client: AsyncClient, product_id: str) -> None:
    for index in range(2):
        await client.post(
            ORDERS, json=order_body(product_id), headers={"Idempotency-Key": f"api-list-000{index}"}
        )
    response = await client.get(ORDERS, params={"email": "ADA@example.com", "page_size": 1})
    page = response.json()
    assert (page["total"], page["total_pages"], len(page["items"])) == (2, 2, 1)
    assert page["items"][0]["item_count"] == 1
    assert (await client.get(ORDERS, params={"email": "nobody@example.com"})).json()["total"] == 0
