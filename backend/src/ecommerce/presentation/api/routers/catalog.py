from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from ecommerce.application.catalog.use_cases import ArchiveProductCommand
from ecommerce.domain.catalog.category import Category
from ecommerce.presentation.api.dependencies import (
    ContainerDep,
    ExpectedVersionDep,
    MediaUrlsDep,
    etag_for,
)
from ecommerce.presentation.api.schemas.common import PageOut, problem_responses
from ecommerce.presentation.api.schemas.products import (
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductSearchParams,
    ProductUpdate,
)

router = APIRouter(tags=["catalog"])


@router.get("/categories", summary="List product categories")
async def list_categories() -> list[CategoryOut]:
    return [CategoryOut(value=category, label=category.label) for category in Category]


@router.get(
    "/products",
    summary="Search products",
    description=(
        "Full-text and fuzzy search over name, SKU and description with filters, "
        "sorting and page based pagination."
    ),
    responses=problem_responses(422),
)
async def search_products(
    container: ContainerDep, media: MediaUrlsDep, params: Annotated[ProductSearchParams, Query()]
) -> PageOut[ProductOut]:
    page = await container.search_products.execute(params.to_criteria())
    return PageOut[ProductOut].from_page(page, lambda item: ProductOut.from_domain(item, media))


@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
    responses=problem_responses(409, 422),
)
async def create_product(
    container: ContainerDep, media: MediaUrlsDep, body: ProductCreate, response: Response
) -> ProductOut:
    product = await container.create_product.execute(body.to_command())
    response.headers["Location"] = f"/api/v1/products/{product.id}"
    response.headers["ETag"] = etag_for(product.version)
    return ProductOut.from_domain(product, media)


@router.get("/products/{product_id}", summary="Get a product", responses=problem_responses(404))
async def get_product(
    container: ContainerDep, media: MediaUrlsDep, product_id: UUID, response: Response
) -> ProductOut:
    product = await container.get_product.execute(product_id)
    response.headers["ETag"] = etag_for(product.version)
    return ProductOut.from_domain(product, media)


@router.patch(
    "/products/{product_id}",
    summary="Update a product",
    description="Partial update. Send If-Match with the ETag to avoid overwriting newer changes.",
    responses=problem_responses(400, 404, 409, 412, 422),
)
async def update_product(
    *,
    container: ContainerDep,
    media: MediaUrlsDep,
    product_id: UUID,
    body: ProductUpdate,
    version: ExpectedVersionDep,
    response: Response,
) -> ProductOut:
    product = await container.update_product.execute(body.to_command(product_id, version))
    response.headers["ETag"] = etag_for(product.version)
    return ProductOut.from_domain(product, media)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a product",
    description="Soft delete: the product leaves the catalog but past orders keep their history.",
    responses=problem_responses(400, 404, 412),
)
async def archive_product(
    container: ContainerDep, product_id: UUID, version: ExpectedVersionDep
) -> Response:
    await container.archive_product.execute(ArchiveProductCommand(product_id, version))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
