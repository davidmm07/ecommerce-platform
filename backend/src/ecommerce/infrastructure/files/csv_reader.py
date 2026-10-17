import csv
import io
import re

from ecommerce.application.errors import InvalidImportFile
from ecommerce.application.imports.table import ProductTable, RawProductRow

_HEADER_SEPARATORS = re.compile(r"[\s-]+")


class CsvProductTableReader:
    def read(self, content: bytes) -> ProductTable:
        text = _decode(content)
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            header = next(reader, None)
            if header is None or not any(cell.strip() for cell in header):
                raise InvalidImportFile("The file is empty or has no header row")
            columns = _columns(header)
            rows: list[RawProductRow] = []
            last_line = reader.line_num
            for cells in reader:
                rows.append(_row(last_line + 1, columns, cells))
                last_line = reader.line_num
        except csv.Error as exc:
            raise InvalidImportFile(f"Malformed CSV near line {reader.line_num}: {exc}") from exc
        return ProductTable(columns=columns, rows=tuple(rows))


def _decode(content: bytes) -> str:
    if not content.strip():
        raise InvalidImportFile("The file is empty")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidImportFile("The file must be UTF-8 encoded") from exc
    if "\x00" in text:
        raise InvalidImportFile("The file looks binary, a CSV text file is expected")
    return text


def _columns(header: list[str]) -> tuple[str, ...]:
    columns = tuple(_HEADER_SEPARATORS.sub("_", cell.strip().lower()) for cell in header)
    named = [column for column in columns if column]
    duplicates = sorted({column for column in named if named.count(column) > 1})
    if duplicates:
        raise InvalidImportFile(f"Duplicated columns: {', '.join(duplicates)}")
    return columns


def _row(line: int, columns: tuple[str, ...], cells: list[str]) -> RawProductRow:
    values = {column: cell for column, cell in zip(columns, cells, strict=False) if column}
    extra = [cell for cell in cells[len(columns) :] if cell.strip()]
    problem = (
        f"expected {len(columns)} fields but found {len(cells)}, check for unquoted commas"
        if extra
        else None
    )
    return RawProductRow(line=line, values=values, problem=problem)
