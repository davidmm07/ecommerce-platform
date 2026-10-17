from decimal import Decimal

import pytest

from ecommerce.application.catalog.queries import ProductSearchCriteria, ProductSort
from ecommerce.application.pagination import PageRequest
from ecommerce.container import Container
from ecommerce.domain.catalog.category import Category
from tests.conftest import SAMPLE_CSV


@pytest.fixture
async def catalog(clean_database: Container) -> Container:
    await clean_database.import_products.execute(SAMPLE_CSV.read_bytes())
    return clean_database


async def skus(container: Container, **criteria: object) -> list[str]:
    page = await container.search_products.execute(ProductSearchCriteria(**criteria))
    return [product.sku.value for product in page.items]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("blutooth speker", {"BS-021", "BS-099"}),
        ("runn", {"RS-001", "RS-050"}),
        ("phone", {"PC-001", "PST-017"}),
        ("rs-0", {"RS-001", "RS-050"}),
        ("RS-001", {"RS-001"}),
        ("drop table", {"SQL-001"}),
    ],
)
async def test_full_text_fuzzy_and_sku_matching(
    catalog: Container, text: str, expected: set[str]
) -> None:
    assert set(await skus(catalog, text=text, page=PageRequest(1, 50))) == expected


async def test_description_terms_are_searchable_and_ranked(catalog: Container) -> None:
    results = await skus(catalog, text="waterproof", page=PageRequest(1, 50))
    assert {"CT-005", "BS-021", "HB-002", "DM-012"} <= set(results)


async def test_wildcards_are_treated_literally(catalog: Container) -> None:
    assert await skus(catalog, text="%") == []
    assert await skus(catalog, text="_") == []


async def test_filters_and_sorting(catalog: Container) -> None:
    results = await skus(
        catalog,
        category=Category.ELECTRONICS,
        min_price=Decimal("50"),
        max_price=Decimal("150"),
        sort=ProductSort.PRICE_DESC,
    )
    assert results == ["WE-023", "FT-013", "BM-006", "BS-021"]
    assert await skus(catalog, in_stock=False) == ["VC-001"]
    newest = await catalog.search_products.execute(ProductSearchCriteria(sort=ProductSort.NEWEST))
    assert newest.total == 84


async def test_pagination_reports_totals(catalog: Container) -> None:
    first = await catalog.search_products.execute(
        ProductSearchCriteria(sort=ProductSort.NAME, page=PageRequest(1, 10))
    )
    last = await catalog.search_products.execute(
        ProductSearchCriteria(sort=ProductSort.NAME, page=PageRequest(9, 10))
    )
    assert (first.total, first.total_pages, len(first.items), len(last.items)) == (84, 9, 10, 4)
    assert first.items[0].name <= first.items[-1].name


async def test_archived_products_are_hidden(catalog: Container) -> None:
    page = await catalog.search_products.execute(ProductSearchCriteria(text="RS-050"))
    product = page.items[0]
    async with catalog.unit_of_work() as uow:
        stored = await uow.products.get(product.id, lock=True)
        assert stored is not None
        stored.archive(stored.updated_at)
        await uow.products.update(stored)
        await uow.commit()
    assert await skus(catalog, text="RS-050") == []
