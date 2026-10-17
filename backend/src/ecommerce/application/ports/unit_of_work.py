from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Self

from ecommerce.application.ports.repositories import OrderRepository, ProductRepository


class UnitOfWork(ABC):
    products: ProductRepository
    orders: OrderRepository

    async def __aenter__(self) -> Self:
        await self._begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            await self.rollback()
        finally:
            await self._end()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    async def _begin(self) -> None: ...

    @abstractmethod
    async def _end(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]
