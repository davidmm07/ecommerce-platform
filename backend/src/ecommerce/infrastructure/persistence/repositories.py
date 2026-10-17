from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ecommerce.application.errors import ConcurrentModification, NotFoundError
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.ordering.order import Order
from ecommerce.infrastructure.persistence.database import translate_persistence_errors
from ecommerce.infrastructure.persistence.mappers import OrderMapper, ProductMapper
from ecommerce.infrastructure.persistence.models import OrderRecord, ProductRecord


class _Tracker[R: ProductRecord | OrderRecord]:
    def __init__(self, session: AsyncSession, model: type[R], resource: str) -> None:
        self._session = session
        self._model = model
        self._resource = resource
        self._records: dict[UUID, R] = {}

    def track(self, record: R) -> R:
        self._records[record.id] = record
        return record

    def track_all(self, records: Sequence[R]) -> Sequence[R]:
        for record in records:
            self.track(record)
        return records

    async def loaded(self, entity_id: UUID, expected_version: int) -> R:
        record = self._records.get(entity_id) or await self._session.get(self._model, entity_id)
        if record is None:
            raise NotFoundError(self._resource.capitalize(), entity_id)
        if record.version != expected_version:
            raise ConcurrentModification(self._resource)
        return self.track(record)

    async def insert(self, record: R) -> R:
        self._session.add(record)
        await self.flush()
        return self.track(record)

    async def flush(self) -> None:
        async with translate_persistence_errors(self._resource):
            await self._session.flush()


class SqlAlchemyProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracker = _Tracker(session, ProductRecord, "product")

    async def add(self, product: Product) -> None:
        record = await self._tracker.insert(ProductMapper.to_record(product))
        product.version = record.version

    async def update(self, product: Product) -> None:
        record = await self._tracker.loaded(product.id, product.version)
        ProductMapper.apply(product, record)
        await self._tracker.flush()
        product.version = record.version

    async def get(self, product_id: UUID, *, lock: bool = False) -> Product | None:
        statement = _active(select(ProductRecord).where(ProductRecord.id == product_id))
        record = (await self._session.scalars(_locked(statement, lock))).one_or_none()
        return ProductMapper.to_domain(self._tracker.track(record)) if record else None

    async def get_by_sku(self, sku: Sku) -> Product | None:
        statement = _active(select(ProductRecord).where(ProductRecord.sku == sku.value))
        record = (await self._session.scalars(statement)).one_or_none()
        return ProductMapper.to_domain(self._tracker.track(record)) if record else None

    async def get_many(
        self,
        product_ids: Collection[UUID],
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> list[Product]:
        if not product_ids:
            return []
        statement = (
            select(ProductRecord)
            .where(ProductRecord.id.in_(set(product_ids)))
            .order_by(ProductRecord.id)
        )
        if not include_archived:
            statement = _active(statement)
        records = (await self._session.scalars(_locked(statement, lock))).all()
        return [ProductMapper.to_domain(record) for record in self._tracker.track_all(records)]

    async def get_many_by_sku(
        self, skus: Collection[Sku], *, lock: bool = False
    ) -> dict[Sku, Product]:
        if not skus:
            return {}
        statement = _active(
            select(ProductRecord)
            .where(ProductRecord.sku.in_({sku.value for sku in skus}))
            .order_by(ProductRecord.id)
        )
        records = (await self._session.scalars(_locked(statement, lock))).all()
        products = (ProductMapper.to_domain(r) for r in self._tracker.track_all(records))
        return {product.sku: product for product in products}


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tracker = _Tracker(session, OrderRecord, "order")

    async def add(self, order: Order) -> None:
        record = await self._tracker.insert(OrderMapper.to_record(order))
        order.version = record.version

    async def update(self, order: Order) -> None:
        record = await self._tracker.loaded(order.id, order.version)
        OrderMapper.apply(order, record)
        await self._tracker.flush()
        order.version = record.version

    async def get(self, order_id: UUID, *, lock: bool = False) -> Order | None:
        statement = _with_lines(select(OrderRecord).where(OrderRecord.id == order_id))
        record = (await self._session.scalars(_locked(statement, lock))).one_or_none()
        return OrderMapper.to_domain(self._tracker.track(record)) if record else None

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        statement = _with_lines(select(OrderRecord).where(OrderRecord.idempotency_key == key))
        record = (await self._session.scalars(statement)).one_or_none()
        return OrderMapper.to_domain(self._tracker.track(record)) if record else None


def _active(statement: Select[ProductRecord]) -> Select[ProductRecord]:
    return statement.where(ProductRecord.archived_at.is_(None))


def _with_lines(statement: Select[OrderRecord]) -> Select[OrderRecord]:
    return statement.options(selectinload(OrderRecord.lines))


def _locked[R: ProductRecord | OrderRecord](statement: Select[R], lock: bool) -> Select[R]:
    if not lock:
        return statement
    return statement.with_for_update().execution_options(populate_existing=True)
