import argparse
import asyncio
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ecommerce.application.catalog.images import (
    ImageCreditInput,
    ImageImportOutcome,
    ImageImportResult,
    ImageSource,
)
from ecommerce.application.errors import ApplicationError
from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.container import Container
from ecommerce.domain.errors import DomainError
from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.logging import configure_logging

MANIFEST_COLUMNS = ("sku", "image_url")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ecommerce", description="Operational commands")
    commands = parser.add_subparsers(dest="command", required=True)
    products_parser = commands.add_parser("import-products", help="Import products from a CSV file")
    products_parser.add_argument("path", type=Path)
    products_parser.add_argument("--dry-run", action="store_true")
    images_parser = commands.add_parser(
        "import-images",
        help="Download product images listed in a CSV manifest (sku, image_url and credits)",
    )
    images_parser.add_argument("manifest", type=Path)
    images_parser.add_argument(
        "--strict", action="store_true", help="Exit with an error when any image fails"
    )
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging("WARNING", settings.log_format)
    try:
        if args.command == "import-images":
            sources = _read_manifest(args.manifest)
            results = asyncio.run(_import_images(settings, sources))
            summary = _image_summary(results)
            sys.stdout.write(json.dumps(summary, indent=2) + "\n")
            failed = bool(summary[ImageImportOutcome.FAILED.value])
            return 1 if failed and args.strict else 0
        content = args.path.read_bytes()
        report = asyncio.run(_import_products(settings, content, dry_run=args.dry_run))
    except (DomainError, ApplicationError, OSError, ValueError, csv.Error) as exc:
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


async def _import_images(settings: Settings, sources: list[ImageSource]) -> list[ImageImportResult]:
    container = Container(settings)
    try:
        return await container.import_product_images.execute(sources)
    finally:
        await container.aclose()


def _read_manifest(path: Path) -> list[ImageSource]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in MANIFEST_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} is missing the columns {', '.join(missing)}")
        return [_source_from(row) for row in reader if (row.get("sku") or "").strip()]


def _source_from(row: dict[str, str]) -> ImageSource:
    author = (row.get("author") or "").strip()
    credit = (
        ImageCreditInput(
            author=author,
            license=(row.get("license") or "").strip(),
            source_url=(row.get("source_url") or "").strip(),
            license_url=(row.get("license_url") or "").strip() or None,
        )
        if author
        else None
    )
    return ImageSource(sku=row["sku"].strip(), url=row["image_url"].strip(), credit=credit)


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
        "total": len(results),
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
