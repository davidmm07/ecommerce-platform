import re
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import selectinload

from ecommerce.application.catalog.queries import ProductSearchCriteria, ProductSort
from ecommerce.application.pagination import Page, PageRequest
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.ordering.order import Order
from ecommerce.infrastructure.persistence.database import SessionFactory
from ecommerce.infrastructure.persistence.mappers import OrderMapper, ProductMapper
from ecommerce.infrastructure.persistence.models import OrderRecord, ProductRecord

_TERM = re.compile(r"[^\W_]+")
_MAX_TERMS = 8


def prefix_query(text: str) -> str | None:
    terms = _TERM.findall(text.casefold())[:_MAX_TERMS]
    return " & ".join(f"{term}:*" for term in terms) or None


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlAlchemyCatalogReadModel:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def search(self, criteria: ProductSearchCriteria) -> Page[Product]:
        filters, rank = _filters_and_rank(criteria)
        count = select(func.count()).select_from(ProductRecord).where(*filters)
        statement: Select[ProductRecord] = (
            select(ProductRecord)
            .where(*filters)
            .order_by(*_ordering(criteria.effective_sort, rank))
            .limit(criteria.page.size)
            .offset(criteria.page.offset)
        )
        async with self._session_factory() as session:
            total = await session.scalar(count) or 0
            records = (await session.scalars(statement)).all()
        return Page(
            items=[ProductMapper.to_domain(record) for record in records],
            total=total,
            request=criteria.page,
        )


class SqlAlchemyOrderReadModel:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def list_page(self, request: PageRequest, *, email: str | None = None) -> Page[Order]:
        filters = [OrderRecord.customer_email == email] if email else []
        count = select(func.count()).select_from(OrderRecord).where(*filters)
        statement = (
            select(OrderRecord)
            .where(*filters)
            .options(selectinload(OrderRecord.lines))
            .order_by(OrderRecord.created_at.desc(), OrderRecord.id.desc())
            .limit(request.size)
            .offset(request.offset)
        )
        async with self._session_factory() as session:
            total = await session.scalar(count) or 0
            records = (await session.scalars(statement)).all()
        return Page(
            items=[OrderMapper.to_domain(record) for record in records],
            total=total,
            request=request,
        )


def _filters_and_rank(
    criteria: ProductSearchCriteria,
) -> tuple[list[ColumnElement[bool]], ColumnElement[Any] | None]:
    filters: list[ColumnElement[bool]] = [ProductRecord.archived_at.is_(None)]
    rank: ColumnElement[Any] | None = None
    if criteria.text:
        pattern = escape_like(criteria.text)
        matches: list[ColumnElement[bool]] = [
            ProductRecord.name.ilike(f"%{pattern}%", escape="\\"),
            ProductRecord.sku.ilike(f"{pattern}%", escape="\\"),
            ProductRecord.name.op("%")(criteria.text),
        ]
        rank = func.similarity(ProductRecord.name, criteria.text)
        terms = prefix_query(criteria.text)
        if terms:
            ts_query = func.to_tsquery("english", terms)
            matches.append(ProductRecord.search_vector.op("@@")(ts_query))
            rank = rank + func.ts_rank(ProductRecord.search_vector, ts_query)
        filters.append(or_(*matches))
    if criteria.category is not None:
        filters.append(ProductRecord.category == criteria.category.value)
    if criteria.min_price is not None:
        filters.append(ProductRecord.price >= criteria.min_price)
    if criteria.max_price is not None:
        filters.append(ProductRecord.price <= criteria.max_price)
    if criteria.in_stock is True:
        filters.append(ProductRecord.stock > 0)
    elif criteria.in_stock is False:
        filters.append(ProductRecord.stock == 0)
    return filters, rank


def _ordering(sort: ProductSort, rank: ColumnElement[Any] | None) -> list[ColumnElement[Any]]:
    tie_breaker = ProductRecord.id.asc()
    match sort:
        case ProductSort.RELEVANCE if rank is not None:
            return [rank.desc(), ProductRecord.name.asc(), tie_breaker]
        case ProductSort.PRICE_ASC:
            return [ProductRecord.price.asc(), ProductRecord.name.asc(), tie_breaker]
        case ProductSort.PRICE_DESC:
            return [ProductRecord.price.desc(), ProductRecord.name.asc(), tie_breaker]
        case ProductSort.NEWEST:
            return [ProductRecord.created_at.desc(), tie_breaker]
        case _:
            return [ProductRecord.name.asc(), tie_breaker]
