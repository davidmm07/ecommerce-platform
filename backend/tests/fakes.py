import copy
from collections.abc import Collection
from dataclasses import dataclass, field
from uuid import UUID

from ecommerce.application.errors import (
    ConcurrentModification,
    DuplicateSku,
    NotFoundError,
    RequestInProgress,
)
from ecommerce.application.ports.media import ImageVariant, ProcessedImage
from ecommerce.application.ports.payments import ChargeRequest, ChargeResult, PaymentGatewayError
from ecommerce.application.ports.unit_of_work import UnitOfWork
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.ordering.order import Order


@dataclass
class InMemoryDatabase:
    products: dict[UUID, Product] = field(default_factory=dict)
    orders: dict[UUID, Order] = field(default_factory=dict)
    commits: int = 0

    def seed(self, *products: Product) -> None:
        for product in products:
            self.products[product.id] = copy.deepcopy(product)

    def product(self, product_id: UUID) -> Product:
        return self.products[product_id]


class InMemoryProductRepository:
    def __init__(self, store: dict[UUID, Product]) -> None:
        self._store = store

    async def add(self, product: Product) -> None:
        if any(p.sku == product.sku and not p.is_archived for p in self._store.values()):
            raise DuplicateSku(product.sku.value)
        product.version = 1
        self._store[product.id] = product

    async def update(self, product: Product) -> None:
        if product.id not in self._store:
            raise NotFoundError("Product", product.id)
        if self._store[product.id] is not product:
            raise ConcurrentModification("product")
        product.version += 1

    async def get(self, product_id: UUID, *, lock: bool = False) -> Product | None:
        product = self._store.get(product_id)
        return product if product and not product.is_archived else None

    async def get_by_sku(self, sku: Sku) -> Product | None:
        return next((p for p in self._store.values() if p.sku == sku and not p.is_archived), None)

    async def get_many(
        self,
        product_ids: Collection[UUID],
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> list[Product]:
        return [
            product
            for product_id in sorted(set(product_ids))
            if (product := self._store.get(product_id))
            and (include_archived or not product.is_archived)
        ]

    async def get_many_by_sku(
        self, skus: Collection[Sku], *, lock: bool = False
    ) -> dict[Sku, Product]:
        return {p.sku: p for p in self._store.values() if p.sku in set(skus) and not p.is_archived}


class InMemoryOrderRepository:
    def __init__(self, store: dict[UUID, Order]) -> None:
        self._store = store

    async def add(self, order: Order) -> None:
        if any(o.idempotency_key == order.idempotency_key for o in self._store.values()):
            raise RequestInProgress()
        self._store[order.id] = order

    async def update(self, order: Order) -> None:
        if order.id not in self._store:
            raise NotFoundError("Order", order.id)
        order.version += 1

    async def get(self, order_id: UUID, *, lock: bool = False) -> Order | None:
        return self._store.get(order_id)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        return next((o for o in self._store.values() if o.idempotency_key == key), None)


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, database: InMemoryDatabase) -> None:
        self._database = database
        self._products: dict[UUID, Product] = {}
        self._orders: dict[UUID, Order] = {}

    async def commit(self) -> None:
        self._database.products = copy.deepcopy(self._products)
        self._database.orders = copy.deepcopy(self._orders)
        self._database.commits += 1

    async def rollback(self) -> None:
        return None

    async def _begin(self) -> None:
        self._products = copy.deepcopy(self._database.products)
        self._orders = copy.deepcopy(self._database.orders)
        self.products = InMemoryProductRepository(self._products)
        self.orders = InMemoryOrderRepository(self._orders)

    async def _end(self) -> None:
        return None


class FakePaymentGateway:
    def __init__(
        self, *, decline_code: str | None = None, error: PaymentGatewayError | None = None
    ) -> None:
        self.decline_code = decline_code
        self.error = error
        self.requests: list[ChargeRequest] = []

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ChargeResult(
            approved=self.decline_code is None,
            card_brand=request.card.brand.value,
            card_last4=request.card.last4,
            reference=f"fake_{len(self.requests)}",
            decline_code=self.decline_code,
        )


class InMemoryObjectStorage:
    def __init__(self, *, fail_deletes: bool = False) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_deletes = fail_deletes

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def delete(self, keys: Collection[str]) -> None:
        if self.fail_deletes:
            raise OSError("storage unavailable")
        for key in keys:
            self.objects.pop(key, None)


class FakeImageProcessor:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def process(self, data: bytes) -> ProcessedImage:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ProcessedImage(
            width=640,
            height=480,
            placeholder="data:image/webp;base64,AAAA",
            variants=tuple(
                ImageVariant(width, fmt, f"image/{fmt}", data[:8] + fmt.encode())
                for width in (320, 640)
                for fmt in ("avif", "webp")
            ),
        )
