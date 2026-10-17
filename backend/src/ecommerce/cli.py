import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ecommerce.application.catalog.images import ImageFile, ImageImportOutcome, ImageImportResult
from ecommerce.application.errors import ApplicationError
from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.container import Container
from ecommerce.domain.errors import DomainError
from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.logging import configure_logging

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".avif"})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ecommerce", description="Operational commands")
    commands = parser.add_subparsers(dest="command", required=True)
    products_parser = commands.add_parser("import-products", help="Import products from a CSV file")
    products_parser.add_argument("path", type=Path)
    products_parser.add_argument("--dry-run", action="store_true")
    images_parser = commands.add_parser(
        "import-images", help="Attach images named after product SKUs, e.g. RS-001.jpg"
    )
    images_parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging("WARNING", settings.log_format)
    try:
        if args.command == "import-images":
            files = _read_images(args.directory)
            results = asyncio.run(_import_images(settings, files))
            summary = _image_summary(results)
            sys.stdout.write(json.dumps(summary, indent=2) + "\n")
            return 1 if summary[ImageImportOutcome.FAILED.value] else 0
        content = args.path.read_bytes()
        report = asyncio.run(_import_products(settings, content, dry_run=args.dry_run))
    except (DomainError, ApplicationError, OSError) as exc:
        sys.stderr.write(f"import failed: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(_summary(report), indent=2) + "\n")
    return 0


async def _import_products(settings: Settings, content: bytes, *, dry_run: bool) -> ImportReport:
    container = Container(settings)
    try:
        return await container.import_products.execute(content, dry_run=dry_run)
    finally:
        await container.aclose()


async def _import_images(settings: Settings, files: list[ImageFile]) -> list[ImageImportResult]:
    container = Container(settings)
    try:
        return await container.import_product_images.execute(files)
    finally:
        await container.aclose()


def _read_images(directory: Path) -> list[ImageFile]:
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    return [ImageFile(sku=path.stem, content=path.read_bytes()) for path in paths]


def _summary(report: ImportReport) -> dict[str, object]:
    return {
        "dry_run": report.dry_run,
        "total_rows": report.total_rows,
        **{outcome.value: report.count(outcome) for outcome in RowOutcome},
        "issues": [
            {
                "line": row.line,
                "sku": row.sku,
                "outcome": row.outcome.value,
                "messages": row.messages,
            }
            for row in report.rows
            if row.outcome in {RowOutcome.FAILED, RowOutcome.SKIPPED}
        ],
    }


def _image_summary(results: list[ImageImportResult]) -> dict[str, object]:
    return {
        "total_files": len(results),
        **{
            outcome.value: sum(1 for result in results if result.outcome is outcome)
            for outcome in ImageImportOutcome
        },
        "issues": [
            {"sku": result.sku, "outcome": result.outcome.value, "message": result.message}
            for result in results
            if result.outcome in {ImageImportOutcome.NOT_FOUND, ImageImportOutcome.FAILED}
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
