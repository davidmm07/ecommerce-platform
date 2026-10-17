from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from ecommerce.application.catalog.queries import ProductSearchCriteria
from ecommerce.application.pagination import Page, PageRequest
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.ordering.order import Order


class ProductRepository(Protocol):
    async def add(self, product: Product) -> None: ...

    async def update(self, product: Product) -> None: ...

    async def get(self, product_id: UUID, *, lock: bool = False) -> Product | None: ...

    async def get_by_sku(self, sku: Sku) -> Product | None: ...

    async def get_many(
        self,
        product_ids: Collection[UUID],
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> list[Product]: ...

    async def get_many_by_sku(
        self, skus: Collection[Sku], *, lock: bool = False
    ) -> dict[Sku, Product]: ...


class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...

    async def update(self, order: Order) -> None: ...

    async def get(self, order_id: UUID, *, lock: bool = False) -> Order | None: ...

    async def get_by_idempotency_key(self, key: str) -> Order | None: ...


class CatalogReadModel(Protocol):
    async def search(self, criteria: ProductSearchCriteria) -> Page[Product]: ...


class OrderReadModel(Protocol):
    async def list_page(self, request: PageRequest, *, email: str | None = None) -> Page[Order]: ...
