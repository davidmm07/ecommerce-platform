from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RowOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RowResult:
    line: int
    sku: str | None
    outcome: RowOutcome
    messages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportReport:
    dry_run: bool
    rows: tuple[RowResult, ...]

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    def count(self, outcome: RowOutcome) -> int:
        return sum(1 for row in self.rows if row.outcome is outcome)

    @property
    def summary(self) -> dict[RowOutcome, int]:
        return {outcome: self.count(outcome) for outcome in RowOutcome}


@dataclass(slots=True)
class ImportReportBuilder:
    dry_run: bool
    _results: dict[int, RowResult] = field(default_factory=dict)

    def record(self, line: int, sku: str | None, outcome: RowOutcome, *messages: str) -> None:
        self._results[line] = RowResult(line, sku, outcome, messages)

    def build(self) -> ImportReport:
        return ImportReport(
            dry_run=self.dry_run,
            rows=tuple(self._results[line] for line in sorted(self._results)),
        )
