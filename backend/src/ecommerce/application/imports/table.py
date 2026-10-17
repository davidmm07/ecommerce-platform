from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RawProductRow:
    line: int
    values: Mapping[str, str]
    problem: str | None = None

    @property
    def is_blank(self) -> bool:
        return self.problem is None and not any(value.strip() for value in self.values.values())

    def get(self, column: str) -> str:
        return self.values.get(column, "")


@dataclass(frozen=True, slots=True)
class ProductTable:
    columns: tuple[str, ...]
    rows: Sequence[RawProductRow] = field(default_factory=tuple)


class ProductTableReader(Protocol):
    def read(self, content: bytes) -> ProductTable: ...
