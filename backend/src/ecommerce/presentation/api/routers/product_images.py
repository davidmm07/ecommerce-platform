from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from ecommerce.application.catalog.images import (
    RemoveProductImageCommand,
    ReplaceProductImageCommand,
)
from ecommerce.presentation.api.dependencies import (
    ContainerDep,
    ExpectedVersionDep,
    MediaUrlsDep,
    etag_for,
)
from ecommerce.presentation.api.schemas.common import problem_responses
from ecommerce.presentation.api.schemas.products import ProductOut

router = APIRouter(tags=["catalog"])

_GENERIC_TYPES = {"application/octet-stream", ""}


@router.put(
    "/products/{product_id}/image",
    summary="Upload or replace the product image",
    description=(
        "Accepts JPEG, PNG, WebP or AVIF. The server validates the file, fixes the orientation, "
        "strips metadata and stores AVIF and WebP renditions in several widths."
    ),
    responses=problem_responses(400, 404, 409, 412, 413, 415, 422),
)
async def replace_product_image(
    *,
    container: ContainerDep,
    media: MediaUrlsDep,
    product_id: UUID,
    file: Annotated[UploadFile, File(description="The image file")],
    version: ExpectedVersionDep,
    response: Response,
) -> ProductOut:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("image/") and content_type not in _GENERIC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, WebP or AVIF image",
        )
    limit = container.settings.image_max_bytes
    content = await file.read(limit + 1)
    product = await container.replace_product_image.execute(
        ReplaceProductImageCommand(product_id, content, version)
    )
    response.headers["ETag"] = etag_for(product.version)
    return ProductOut.from_domain(product, media)


@router.delete(
    "/products/{product_id}/image",
    summary="Remove the product image",
    responses=problem_responses(400, 404, 409, 412),
)
async def remove_product_image(
    container: ContainerDep,
    media: MediaUrlsDep,
    product_id: UUID,
    version: ExpectedVersionDep,
    response: Response,
) -> ProductOut:
    product = await container.remove_product_image.execute(
        RemoveProductImageCommand(product_id, version)
    )
    response.headers["ETag"] = etag_for(product.version)
    return ProductOut.from_domain(product, media)
