from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm.exc import StaleDataError

from ecommerce.application.errors import (
    ConcurrentModification,
    ConflictError,
    DuplicateSku,
    RequestInProgress,
)

type SessionFactory = async_sessionmaker[AsyncSession]


def create_engine(url: str, *, pool_size: int = 10, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=pool_size,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=echo,
    )


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def database_is_ready(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


@asynccontextmanager
async def translate_persistence_errors(resource: str) -> AsyncIterator[None]:
    try:
        yield
    except StaleDataError as exc:
        raise ConcurrentModification(resource) from exc
    except IntegrityError as exc:
        raise _conflict_for(exc, resource) from exc


def _conflict_for(exc: IntegrityError, resource: str) -> ConflictError:
    constraint = _constraint_name(exc)
    if constraint == "uq_products_sku_active":
        return DuplicateSku(_sku_from(exc))
    if constraint == "uq_orders_idempotency_key":
        return RequestInProgress()
    return ConcurrentModification(resource)


def _constraint_name(exc: IntegrityError) -> str | None:
    cause = getattr(exc.orig, "__cause__", None)
    name = getattr(cause, "constraint_name", None) or getattr(exc.orig, "constraint_name", None)
    return name if isinstance(name, str) else None


def _sku_from(exc: IntegrityError) -> str:
    cause = getattr(exc.orig, "__cause__", None)
    detail = getattr(cause, "detail", None)
    if isinstance(detail, str) and "=(" in detail:
        return detail.split("=(", 1)[1].split(")", 1)[0]
    return "provided"
