from decimal import Decimal
from uuid import uuid4

import pytest

from ecommerce.application.catalog.queries import ProductSearchCriteria, ProductSort
from ecommerce.application.catalog.use_cases import (
    ArchiveProduct,
    ArchiveProductCommand,
    CreateProduct,
    CreateProductCommand,
    GetProduct,
    SearchProducts,
    UpdateProduct,
    UpdateProductCommand,
)
from ecommerce.application.errors import DuplicateSku, NotFoundError, VersionMismatch
from ecommerce.application.pagination import Page, PageRequest
from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.errors import DomainValidationError
from tests.factories import FixedClock, make_product
from tests.fakes import InMemoryDatabase, InMemoryUnitOfWork


@pytest.fixture
def database() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


def uow_factory(database: InMemoryDatabase) -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(database)


def create_command(**overrides: object) -> CreateProductCommand:
    values: dict[str, object] = {
        "sku": "rs-001",
        "name": "Running Shoes",
        "description": "Lightweight",
        "category": "footwear",
        "price": Decimal("89.99"),
        "stock": 150,
        "weight_kg": Decimal("0.35"),
    }
    values.update(overrides)
    return CreateProductCommand(**values)


class TestCreateProduct:
    async def test_creates_a_normalized_product(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        use_case = CreateProduct(
            uow_factory=lambda: uow_factory(database), clock=clock, new_id=uuid4
        )
        product = await use_case.execute(create_command())
        assert product.sku.value == "RS-001"
        assert product.version == 1
        assert database.product(product.id).name == "Running Shoes"

    async def test_rejects_duplicate_skus(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        database.seed(make_product("RS-001"))
        use_case = CreateProduct(
            uow_factory=lambda: uow_factory(database), clock=clock, new_id=uuid4
        )
        with pytest.raises(DuplicateSku):
            await use_case.execute(create_command())
        assert database.commits == 0

    async def test_reports_sku_and_detail_errors_together(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        use_case = CreateProduct(
            uow_factory=lambda: uow_factory(database), clock=clock, new_id=uuid4
        )
        with pytest.raises(DomainValidationError) as caught:
            await use_case.execute(create_command(sku="?", price=Decimal("-1")))
        assert {error.field for error in caught.value.errors} == {"sku", "price"}


class TestUpdateProduct:
    async def test_applies_a_partial_update(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        product = make_product()
        database.seed(product)
        clock.advance(minutes=5)
        use_case = UpdateProduct(uow_factory=lambda: uow_factory(database), clock=clock)
        updated = await use_case.execute(
            UpdateProductCommand(product_id=product.id, price=Decimal("94.99"), expected_version=1)
        )
        stored = database.product(product.id)
        assert (stored.price.amount, stored.name, stored.version) == (
            Decimal("94.99"),
            "Running Shoes",
            2,
        )
        assert updated.updated_at == clock.now()

    async def test_no_op_updates_do_not_bump_the_version(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        product = make_product()
        database.seed(product)
        use_case = UpdateProduct(uow_factory=lambda: uow_factory(database), clock=clock)
        await use_case.execute(UpdateProductCommand(product_id=product.id, name="Running Shoes"))
        assert database.product(product.id).version == 1
        assert database.commits == 0

    async def test_refuses_stale_versions(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        product = make_product()
        database.seed(product)
        use_case = UpdateProduct(uow_factory=lambda: uow_factory(database), clock=clock)
        with pytest.raises(VersionMismatch) as caught:
            await use_case.execute(
                UpdateProductCommand(product_id=product.id, stock=1, expected_version=7)
            )
        assert caught.value.details() == {"expected_version": 7, "current_version": 1}

    async def test_unknown_products_are_not_found(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        use_case = UpdateProduct(uow_factory=lambda: uow_factory(database), clock=clock)
        with pytest.raises(NotFoundError):
            await use_case.execute(UpdateProductCommand(product_id=uuid4(), stock=1))


class TestArchiveAndGet:
    async def test_archived_products_disappear(
        self, database: InMemoryDatabase, clock: FixedClock
    ) -> None:
        product = make_product()
        database.seed(product)
        await ArchiveProduct(uow_factory=lambda: uow_factory(database), clock=clock).execute(
            ArchiveProductCommand(product.id)
        )
        assert database.product(product.id).is_archived
        with pytest.raises(NotFoundError):
            await GetProduct(uow_factory=lambda: uow_factory(database)).execute(product.id)

    async def test_get_returns_active_products(self, database: InMemoryDatabase) -> None:
        product = make_product()
        database.seed(product)
        found = await GetProduct(uow_factory=lambda: uow_factory(database)).execute(product.id)
        assert found.id == product.id


class TestSearch:
    async def test_delegates_to_the_read_model(self) -> None:
        product = make_product()
        seen: list[ProductSearchCriteria] = []

        class StubCatalog:
            async def search(self, criteria: ProductSearchCriteria) -> Page[Product]:
                seen.append(criteria)
                return Page(items=[product], total=1, request=criteria.page)

        criteria = ProductSearchCriteria(text="  running   shoes ", category=Category.FOOTWEAR)
        page = await SearchProducts(catalog=StubCatalog()).execute(criteria)
        assert page.items == [product]
        assert seen[0].text == "running shoes"
        assert seen[0].effective_sort is ProductSort.RELEVANCE

    def test_criteria_validation(self) -> None:
        assert ProductSearchCriteria(text="   ").effective_sort is ProductSort.NAME
        with pytest.raises(DomainValidationError) as caught:
            ProductSearchCriteria(text="x" * 101, min_price=Decimal("10"), max_price=Decimal("5"))
        assert {error.field for error in caught.value.errors} == {"q", "min_price"}
        with pytest.raises(DomainValidationError):
            ProductSearchCriteria(min_price=Decimal("-1"))

    def test_page_request_limits(self) -> None:
        assert PageRequest(3, 20).offset == 40
        assert Page(items=[], total=41, request=PageRequest(1, 20)).total_pages == 3
        with pytest.raises(DomainValidationError):
            PageRequest(0, 101)
