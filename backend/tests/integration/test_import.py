from sqlalchemy import func, select, text

from ecommerce.application.catalog.queries import ProductSearchCriteria
from ecommerce.application.imports.report import RowOutcome
from ecommerce.container import Container
from ecommerce.infrastructure.persistence.models import ProductRecord
from tests.conftest import SAMPLE_CSV


async def product_count(container: Container) -> int:
    async with container.engine.connect() as connection:
        return int(await connection.scalar(select(func.count()).select_from(ProductRecord)) or 0)


async def test_sample_import_is_atomic_and_repeatable(clean_database: Container) -> None:
    content = SAMPLE_CSV.read_bytes()

    first = await clean_database.import_products.execute(content)
    second = await clean_database.import_products.execute(content)

    assert first.count(RowOutcome.CREATED) == 83
    assert second.count(RowOutcome.CREATED) == 0
    assert second.count(RowOutcome.UNCHANGED) == 83
    assert await product_count(clean_database) == 83


async def test_injection_payloads_are_rejected_and_quotes_stay_safe(
    clean_database: Container,
) -> None:
    header = b"name,sku,description,category,price,stock,weight_kg\n"
    report = await clean_database.import_products.execute(
        header
        + b"Robert'); DROP TABLE products;--,SQL-001,Test,Games,9.99,50,0.5\n"
        + b'Robert\'s Board Game,RBG-001,"It\'s ""fun""; really",Games,9.99,50,0.5\n'
    )
    async with clean_database.engine.connect() as connection:
        name = await connection.scalar(text("SELECT name FROM products WHERE sku = 'RBG-001'"))
        description = await connection.scalar(
            text("SELECT description FROM products WHERE sku = 'RBG-001'")
        )
        tables = await connection.scalar(text("SELECT to_regclass('public.products')::text"))
    assert [row.outcome for row in report.rows] == [RowOutcome.FAILED, RowOutcome.CREATED]
    assert (name, description) == ("Robert's Board Game", 'It\'s "fun"; really')
    assert tables == "products"


async def test_dry_run_rolls_back_everything(clean_database: Container) -> None:
    report = await clean_database.import_products.execute(SAMPLE_CSV.read_bytes(), dry_run=True)
    assert report.count(RowOutcome.CREATED) == 83
    assert await product_count(clean_database) == 0


async def test_updates_are_detected_against_the_database(clean_database: Container) -> None:
    header = b"name,sku,description,category,price,stock,weight_kg\n"
    await clean_database.import_products.execute(
        header + b"Desk Lamp,DL-007,LED lamp,Home & Office,45.50,5,2.1\n"
    )
    report = await clean_database.import_products.execute(
        header + b"Desk Lamp,DL-007,LED lamp,Home & Office,39.99,5,2.1\n"
    )
    assert report.rows[0].outcome is RowOutcome.UPDATED
    page = await clean_database.search_products.execute(ProductSearchCriteria(text="DL-007"))
    assert str(page.items[0].price.amount) == "39.99"
    assert page.items[0].version == 2
