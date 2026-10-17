from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ecommerce.container import Container
from ecommerce.presentation.api.app import create_app


@pytest.fixture(scope="session")
def app(container: Container) -> FastAPI:
    return create_app(container)


@pytest.fixture
async def client(app: FastAPI, clean_database: Container) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def product_payload() -> dict[str, object]:
    return {
        "sku": "rs-001",
        "name": "Running Shoes",
        "description": "Lightweight running shoes for daily training",
        "category": "footwear",
        "price": "89.99",
        "stock": 150,
        "weight_kg": "0.35",
    }
