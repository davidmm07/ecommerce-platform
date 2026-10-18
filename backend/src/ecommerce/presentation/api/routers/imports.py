from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from ecommerce.presentation.api.dependencies import ContainerDep
from ecommerce.presentation.api.schemas.common import problem_responses
from ecommerce.presentation.api.schemas.imports import ImportReportOut

router = APIRouter(tags=["imports"])

_ACCEPTED_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}


@router.post(
    "/product-imports",
    summary="Import products from a CSV file",
    description=(
        "Creates or updates products by SKU. Valid rows are applied in one transaction, "
        "invalid rows are reported with the reason. When the optional image_url column is "
        "filled, the image is downloaded and processed after the products are saved, and a "
        "failed download is reported without undoing the product. Use dry_run to validate "
        "without saving or downloading."
    ),
    responses=problem_responses(413, 415, 422),
)
async def import_products(
    container: ContainerDep,
    file: Annotated[
        UploadFile,
        File(
            description="CSV with the columns name, sku, description, category, price, "
            "stock and weight_kg, plus the optional image_url, image_author, image_license, "
            "image_license_url and image_source_url"
        ),
    ],
    dry_run: Annotated[bool, Query(description="Validate and report without saving")] = False,
) -> ImportReportOut:
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    filename = (file.filename or "").lower()
    if content_type not in _ACCEPTED_TYPES or (filename and not filename.endswith(".csv")):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a .csv file",
        )
    limit = container.settings.import_max_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The file must not exceed {limit} bytes",
        )
    report = await container.import_products.execute(content, dry_run=dry_run)
    return ImportReportOut.from_report(report)
