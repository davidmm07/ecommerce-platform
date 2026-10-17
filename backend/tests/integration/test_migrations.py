from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, text

from ecommerce.container import Container
from ecommerce.infrastructure.persistence.models import Base
from tests.conftest import BACKEND_DIR

EXPECTED_CHECKS = {
    "ck_order_lines_quantity_positive",
    "ck_orders_status_known",
    "ck_orders_total_consistent",
    "ck_products_category_known",
    "ck_products_image_is_object",
    "ck_products_price_positive",
    "ck_products_stock_non_negative",
    "ck_products_weight_non_negative",
}


def _differences(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def test_schema_matches_the_models(clean_database: Container) -> None:
    async with clean_database.engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
            )
        )
        checks = {row[0] for row in rows}
        differences = await connection.run_sync(_differences)
    assert checks == EXPECTED_CHECKS
    assert differences == []


def test_migrations_downgrade_and_upgrade_cleanly(migrated_database: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", migrated_database.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "0001")
    command.upgrade(config, "head")
