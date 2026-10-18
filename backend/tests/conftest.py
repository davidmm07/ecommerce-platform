import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

from ecommerce.application.errors import ImageSourceUnavailable
from ecommerce.container import Container
from ecommerce.infrastructure.config import Settings
from tests.factories import FixedClock
from tests.fakes import FakeImageFetcher
from tests.images import jpeg_bytes

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_CSV = BACKEND_DIR.parent / "data" / "products-sample.csv"
SAMPLE_IMAGES_CSV = BACKEND_DIR.parent / "data" / "products-sample-images.csv"
POSTGRES_IMAGE = "postgres:17-alpine"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if {"integration", "api"} & set(item.path.parts):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    configured = os.environ.get("TEST_DATABASE_URL")
    if configured:
        yield configured
        return
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return database_url


@pytest.fixture(scope="session")
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture(scope="session")
def media_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("media")


@pytest.fixture(scope="session")
def image_fetcher() -> FakeImageFetcher:
    return FakeImageFetcher(
        {
            "https://images.example.com/lamp.jpg": jpeg_bytes(900, 600),
            "https://images.example.com/missing.jpg": ImageSourceUnavailable(
                "The image URL answered 404"
            ),
        }
    )


@pytest.fixture(scope="session")
async def container(
    migrated_database: str, clock: FixedClock, media_root: Path, image_fetcher: FakeImageFetcher
) -> AsyncIterator[Container]:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=migrated_database,
        database_pool_size=20,
        log_level="WARNING",
        log_format="text",
        payment_latency_ms=0,
        import_max_bytes=64 * 1024,
        import_max_rows=500,
        media_root=media_root,
        media_serve=True,
        image_max_bytes=2 * 1024 * 1024,
    )
    app_container = Container(settings, clock=clock, image_fetcher=image_fetcher)
    yield app_container
    await app_container.aclose()


@pytest.fixture
async def clean_database(container: Container) -> Container:
    async with container.engine.begin() as connection:
        await connection.execute(text("TRUNCATE order_lines, orders, products"))
    return container
