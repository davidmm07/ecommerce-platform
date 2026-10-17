from pydantic import Field

from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.presentation.api.schemas.common import ApiModel


class ImportSummaryOut(ApiModel):
    total_rows: int = Field(examples=[97])
    created: int = Field(examples=[80])
    updated: int = Field(examples=[0])
    unchanged: int = Field(examples=[0])
    skipped: int = Field(examples=[5])
    failed: int = Field(examples=[12])


class RowResultOut(ApiModel):
    line: int = Field(examples=[7])
    sku: str | None = Field(examples=["YM-015"])
    outcome: RowOutcome
    messages: list[str] = Field(examples=[["price: 'free' is not a valid decimal number"]])


class ImportReportOut(ApiModel):
    dry_run: bool
    summary: ImportSummaryOut
    rows: list[RowResultOut]

    @classmethod
    def from_report(cls, report: ImportReport) -> "ImportReportOut":
        return cls(
            dry_run=report.dry_run,
            summary=ImportSummaryOut(
                total_rows=report.total_rows,
                created=report.count(RowOutcome.CREATED),
                updated=report.count(RowOutcome.UPDATED),
                unchanged=report.count(RowOutcome.UNCHANGED),
                skipped=report.count(RowOutcome.SKIPPED),
                failed=report.count(RowOutcome.FAILED),
            ),
            rows=[
                RowResultOut(
                    line=row.line, sku=row.sku, outcome=row.outcome, messages=list(row.messages)
                )
                for row in report.rows
            ],
        )
