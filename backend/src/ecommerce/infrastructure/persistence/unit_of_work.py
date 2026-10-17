from sqlalchemy.ext.asyncio import AsyncSession

from ecommerce.application.ports.unit_of_work import UnitOfWork
from ecommerce.infrastructure.persistence.database import (
    SessionFactory,
    translate_persistence_errors,
)
from ecommerce.infrastructure.persistence.repositories import (
    SqlAlchemyOrderRepository,
    SqlAlchemyProductRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def commit(self) -> None:
        async with translate_persistence_errors("resource"):
            await self._current().commit()

    async def rollback(self) -> None:
        await self._current().rollback()

    async def _begin(self) -> None:
        session = self._session_factory()
        self._session = session
        self.products = SqlAlchemyProductRepository(session)
        self.orders = SqlAlchemyOrderRepository(session)

    async def _end(self) -> None:
        await self._current().close()
        self._session = None

    def _current(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("The unit of work is not active, use it with 'async with'")
        return self._session
