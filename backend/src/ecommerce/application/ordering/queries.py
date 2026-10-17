from uuid import UUID

from ecommerce.application.errors import NotFoundError
from ecommerce.application.pagination import Page, PageRequest
from ecommerce.application.ports.repositories import OrderReadModel
from ecommerce.application.ports.unit_of_work import UnitOfWorkFactory
from ecommerce.domain.ordering.order import Order


class GetOrder:
    def __init__(self, *, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, order_id: UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
        if order is None:
            raise NotFoundError("Order", order_id)
        return order


class ListOrders:
    def __init__(self, *, orders: OrderReadModel) -> None:
        self._orders = orders

    async def execute(self, request: PageRequest, *, email: str | None = None) -> Page[Order]:
        normalized_email = email.strip().lower() if email and email.strip() else None
        return await self._orders.list_page(request, email=normalized_email)
