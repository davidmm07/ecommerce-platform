from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from ecommerce import __version__
from ecommerce.container import Container
from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.logging import configure_logging
from ecommerce.presentation.api.media import MediaUrls
from ecommerce.presentation.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from ecommerce.presentation.api.problems import install_problem_handlers
from ecommerce.presentation.api.routers import catalog, health, imports, orders, product_images

API_PREFIX = "/api/v1"


def create_app(container: Container | None = None) -> FastAPI:
    settings = container.settings if container else Settings()
    app_container = container or Container(settings)
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await app_container.aclose()

    app = FastAPI(
        title="E-commerce Platform API",
        version=__version__,
        summary="Catalog management, CSV import, product search and checkout.",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        generate_unique_id_function=_operation_id,
    )
    app.state.container = app_container
    app.state.media_urls = MediaUrls(settings.media_base_url)
    install_problem_handlers(app)

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "If-Match", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["ETag", "Location", "X-Request-ID", "Idempotent-Replayed"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    api = APIRouter(prefix=API_PREFIX)
    for module in (catalog, product_images, imports, orders):
        api.include_router(module.router)
    app.include_router(health.router)
    app.include_router(api)
    if settings.media_serve and settings.media_backend == "local":
        settings.media_root.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
    return app


def _operation_id(route: APIRoute) -> str:
    return route.name
