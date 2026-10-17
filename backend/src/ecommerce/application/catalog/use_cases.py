from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ecommerce.application.catalog.queries import ProductSearchCriteria
from ecommerce.application.errors import DuplicateSku, NotFoundError, VersionMismatch
from ecommerce.application.pagination import Page
from ecommerce.application.ports.repositories import CatalogReadModel
from ecommerce.application.ports.system import Clock, IdFactory
from ecommerce.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from ecommerce.domain.catalog.product import Product, ProductDetails
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import FieldErrors


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateProductCommand:
    sku: str
    name: str
    description: str
    category: str
    price: Decimal
    stock: int
    weight_kg: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateProductCommand:
    product_id: UUID
    expected_version: int | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: Decimal | None = None
    stock: int | None = None
    weight_kg: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ArchiveProductCommand:
    product_id: UUID
    expected_version: int | None = None


class CreateProduct:
    def __init__(self, *, uow_factory: UnitOfWorkFactory, clock: Clock, new_id: IdFactory) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._new_id = new_id

    async def execute(self, command: CreateProductCommand) -> Product:
        errors = FieldErrors()
        with errors.collect("sku"):
            sku = Sku.parse(command.sku)
        with errors.collect():
            details = ProductDetails.build(
                name=command.name,
                description=command.description,
                category=command.category,
                price=command.price,
                stock=command.stock,
                weight_kg=command.weight_kg,
            )
        errors.raise_if_any()
        async with self._uow_factory() as uow:
            if await uow.products.get_by_sku(sku) is not None:
                raise DuplicateSku(sku.value)
            product = Product.create(
                product_id=self._new_id(), sku=sku, details=details, now=self._clock.now()
            )
            await uow.products.add(product)
            await uow.commit()
        return product


class UpdateProduct:
    def __init__(self, *, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: UpdateProductCommand) -> Product:
        async with self._uow_factory() as uow:
            product = await load_for_change(uow, command.product_id, command.expected_version)
            current = product.details
            details = ProductDetails.build(
                name=_pick(command.name, current.name),
                description=_pick(command.description, current.description),
                category=_pick(command.category, current.category.value),
                price=_pick(command.price, current.price.amount),
                stock=_pick(command.stock, current.stock),
                weight_kg=_pick(command.weight_kg, current.weight_kg),
                currency=current.price.currency,
            )
            if product.revise(details, self._clock.now()):
                await uow.products.update(product)
                await uow.commit()
        return product


class ArchiveProduct:
    def __init__(self, *, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, command: ArchiveProductCommand) -> None:
        async with self._uow_factory() as uow:
            product = await load_for_change(uow, command.product_id, command.expected_version)
            product.archive(self._clock.now())
            await uow.products.update(product)
            await uow.commit()


class GetProduct:
    def __init__(self, *, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, product_id: UUID) -> Product:
        async with self._uow_factory() as uow:
            product = await uow.products.get(product_id)
        if product is None:
            raise NotFoundError("Product", product_id)
        return product


class SearchProducts:
    def __init__(self, *, catalog: CatalogReadModel) -> None:
        self._catalog = catalog

    async def execute(self, criteria: ProductSearchCriteria) -> Page[Product]:
        return await self._catalog.search(criteria)


async def load_for_change(
    uow: UnitOfWork, product_id: UUID, expected_version: int | None
) -> Product:
    product = await uow.products.get(product_id, lock=True)
    if product is None:
        raise NotFoundError("Product", product_id)
    if expected_version is not None and expected_version != product.version:
        raise VersionMismatch(expected_version, product.version)
    return product


def _pick[T](candidate: T | None, current: T) -> T:
    return current if candidate is None else candidate
