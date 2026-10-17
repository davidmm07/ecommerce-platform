from ecommerce.application.errors import ImportLimitExceeded, InvalidImportFile
from ecommerce.application.imports.report import ImportReport, ImportReportBuilder, RowOutcome
from ecommerce.application.imports.row_parser import (
    REQUIRED_COLUMNS,
    ProductDraft,
    parse_product_row,
)
from ecommerce.application.imports.table import ProductTable, ProductTableReader
from ecommerce.application.ports.system import Clock, IdFactory
from ecommerce.application.ports.unit_of_work import UnitOfWorkFactory
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import DomainValidationError


class ImportProducts:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        reader: ProductTableReader,
        clock: Clock,
        new_id: IdFactory,
        max_rows: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._reader = reader
        self._clock = clock
        self._new_id = new_id
        self._max_rows = max_rows

    async def execute(self, content: bytes, *, dry_run: bool = False) -> ImportReport:
        table = self._reader.read(content)
        self._check_shape(table)
        report = ImportReportBuilder(dry_run)
        drafts = self._collect_drafts(table, report)
        await self._apply(drafts, report, dry_run=dry_run)
        return report.build()

    def _check_shape(self, table: ProductTable) -> None:
        missing = [column for column in REQUIRED_COLUMNS if column not in table.columns]
        if missing:
            raise InvalidImportFile(f"Missing required columns: {', '.join(missing)}")
        if not table.rows:
            raise InvalidImportFile("The file has a header but no data rows")
        if len(table.rows) > self._max_rows:
            raise ImportLimitExceeded(
                f"The file has {len(table.rows)} rows, the limit is {self._max_rows}"
            )

    def _collect_drafts(
        self, table: ProductTable, report: ImportReportBuilder
    ) -> dict[Sku, ProductDraft]:
        drafts: dict[Sku, ProductDraft] = {}
        for row in table.rows:
            raw_sku = row.get("sku").strip() or None
            if row.problem is not None:
                report.record(row.line, raw_sku, RowOutcome.FAILED, row.problem)
                continue
            if row.is_blank:
                report.record(row.line, None, RowOutcome.SKIPPED, "blank row")
                continue
            try:
                draft = parse_product_row(row)
            except DomainValidationError as exc:
                messages = (f"{error.field}: {error.message}" for error in exc.errors)
                report.record(row.line, raw_sku, RowOutcome.FAILED, *messages)
                continue
            previous = drafts.pop(draft.sku, None)
            if previous is not None and previous.details == draft.details:
                drafts[draft.sku] = previous
                report.record(
                    row.line,
                    draft.sku.value,
                    RowOutcome.SKIPPED,
                    f"exact duplicate of line {previous.line}",
                )
                continue
            if previous is not None:
                report.record(
                    previous.line,
                    previous.sku.value,
                    RowOutcome.SKIPPED,
                    f"superseded by line {row.line}, which has the same SKU",
                )
            drafts[draft.sku] = draft
        return drafts

    async def _apply(
        self, drafts: dict[Sku, ProductDraft], report: ImportReportBuilder, *, dry_run: bool
    ) -> None:
        if not drafts:
            return
        now = self._clock.now()
        async with self._uow_factory() as uow:
            existing = await uow.products.get_many_by_sku(drafts.keys(), lock=True)
            for sku, draft in drafts.items():
                product = existing.get(sku)
                if product is None:
                    product = Product.create(
                        product_id=self._new_id(), sku=sku, details=draft.details, now=now
                    )
                    await uow.products.add(product)
                    outcome = RowOutcome.CREATED
                elif product.revise(draft.details, now):
                    await uow.products.update(product)
                    outcome = RowOutcome.UPDATED
                else:
                    outcome = RowOutcome.UNCHANGED
                report.record(draft.line, sku.value, outcome, *draft.notes)
            if not dry_run:
                await uow.commit()
