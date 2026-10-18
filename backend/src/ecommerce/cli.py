import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ecommerce.application.catalog.images import ImageImportOutcome
from ecommerce.application.errors import ApplicationError
from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.container import Container
from ecommerce.domain.errors import DomainError
from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.logging import configure_logging


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ecommerce", description="Operational commands")
    commands = parser.add_subparsers(dest="command", required=True)
    products_parser = commands.add_parser(
        "import-products",
        help="Import products from a CSV file, downloading images from optional image columns",
    )
    products_parser.add_argument("path", type=Path)
    products_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging("WARNING", settings.log_format)
    try:
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


def _summary(report: ImportReport) -> dict[str, object]:
    return {
        "dry_run": report.dry_run,
        "total_rows": report.total_rows,
        **{outcome.value: report.count(outcome) for outcome in RowOutcome},
        "images": {outcome.value: count for outcome, count in report.image_summary.items()},
        "issues": [
            {
                "line": row.line,
                "sku": row.sku,
                "outcome": row.outcome.value,
                "image": row.image.value if row.image else None,
                "messages": row.messages,
            }
            for row in report.rows
            if row.outcome in {RowOutcome.FAILED, RowOutcome.SKIPPED}
            or row.image is ImageImportOutcome.FAILED
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
