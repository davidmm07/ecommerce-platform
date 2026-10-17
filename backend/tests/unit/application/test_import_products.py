from uuid import uuid4

import pytest

from ecommerce.application.errors import ImportLimitExceeded, InvalidImportFile
from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.application.imports.row_parser import parse_decimal, parse_integer
from ecommerce.application.imports.use_case import ImportProducts
from ecommerce.domain.errors import InvalidValue
from ecommerce.infrastructure.files.csv_reader import CsvProductTableReader
from tests.conftest import SAMPLE_CSV
from tests.factories import FixedClock, make_product
from tests.fakes import InMemoryDatabase, InMemoryUnitOfWork

HEADER = "name,sku,description,category,price,stock,weight_kg\n"


def importer(database: InMemoryDatabase, *, max_rows: int = 100) -> ImportProducts:
    return ImportProducts(
        uow_factory=lambda: InMemoryUnitOfWork(database),
        reader=CsvProductTableReader(),
        clock=FixedClock(),
        new_id=uuid4,
        max_rows=max_rows,
    )


def outcomes(report: ImportReport) -> dict[int, tuple[RowOutcome, tuple[str, ...]]]:
    return {row.line: (row.outcome, row.messages) for row in report.rows}


async def run(database: InMemoryDatabase, body: str, *, dry_run: bool = False) -> ImportReport:
    return await importer(database).execute((HEADER + body).encode(), dry_run=dry_run)


async def test_imports_the_provided_sample_file() -> None:
    database = InMemoryDatabase()
    report = await importer(database).execute(SAMPLE_CSV.read_bytes())
    rows = outcomes(report)

    assert report.total_rows == 97
    assert report.summary == {
        RowOutcome.CREATED: 83,
        RowOutcome.UPDATED: 0,
        RowOutcome.UNCHANGED: 0,
        RowOutcome.SKIPPED: 5,
        RowOutcome.FAILED: 9,
    }
    assert len(database.products) == 83
    assert rows[7] == (RowOutcome.FAILED, ("price: 'free' is not a valid decimal number",))
    assert rows[16] == (RowOutcome.FAILED, ("stock: must not be negative",))
    assert rows[20] == (RowOutcome.FAILED, ("name: must be plain text without HTML markup",))
    assert rows[25] == (RowOutcome.FAILED, ("name: is required",))
    assert rows[29] == (
        RowOutcome.FAILED,
        ("name: looks like an SQL injection payload, use plain product text",),
    )
    assert rows[41] == (RowOutcome.FAILED, ("name: is required",))
    assert rows[47] == (RowOutcome.FAILED, ("price: must be greater than 0",))
    assert rows[50] == (RowOutcome.FAILED, ("weight_kg: is required",))
    assert rows[52] == (RowOutcome.FAILED, ("category: is required",))
    assert rows[4] == (RowOutcome.CREATED, ("price: currency symbol removed from '$29.99'",))
    assert rows[2][0] is RowOutcome.SKIPPED
    assert rows[36][0] is RowOutcome.CREATED
    assert rows[62] == rows[63] == (RowOutcome.SKIPPED, ("blank row",))

    by_sku = {product.sku.value: product for product in database.products.values()}
    assert by_sku["RS-001"].description.startswith("Updated lightweight shoes")
    assert str(by_sku["BS-021"].price.amount) == "59.99"
    assert "SQL-001" not in by_sku
    assert by_sku["CI-001"].name == "Comma, In Product Name"
    assert by_sku["QI-001"].name == 'Quote "Inside" Name'
    assert by_sku["WB-033"].description.endswith("24hrs" + chr(0x2122))


async def test_later_rows_supersede_earlier_ones_with_the_same_sku() -> None:
    database = InMemoryDatabase()
    report = await run(
        database,
        "Speaker,BS-021,v1,Electronics,59.99,110,0.8\n"
        "Speaker,BS-021,v2,Electronics,49.99,200,0.75\n"
        "Speaker,BS-021,v1,Electronics,59.99,110,0.8\n"
        "Speaker,BS-021,v1,Electronics,59.99,110,0.8\n",
    )
    assert outcomes(report) == {
        2: (RowOutcome.SKIPPED, ("superseded by line 3, which has the same SKU",)),
        3: (RowOutcome.SKIPPED, ("superseded by line 4, which has the same SKU",)),
        4: (RowOutcome.CREATED, ()),
        5: (RowOutcome.SKIPPED, ("exact duplicate of line 4",)),
    }


async def test_upserts_against_existing_products() -> None:
    database = InMemoryDatabase()
    database.seed(make_product("RS-001", price="89.99"), make_product("LW-019", name="Wallet"))
    report = await run(
        database,
        "Running Shoes,RS-001,Lightweight running shoes for daily training,Footwear,94.99,10,0.35\n"
        "Wallet,LW-019,Lightweight running shoes for daily training,Footwear,89.99,10,0.35\n",
    )
    assert [row.outcome for row in report.rows] == [RowOutcome.UPDATED, RowOutcome.UNCHANGED]
    updated = next(p for p in database.products.values() if p.sku.value == "RS-001")
    assert str(updated.price.amount) == "94.99"
    assert updated.version == 2


async def test_dry_run_reports_without_saving() -> None:
    database = InMemoryDatabase()
    report = await run(database, "Mat,YM-001,,Sports,10.00,1,1\n", dry_run=True)
    assert report.dry_run
    assert report.rows[0].outcome is RowOutcome.CREATED
    assert database.products == {}
    assert database.commits == 0


async def test_rows_with_extra_fields_are_rejected() -> None:
    report = await run(InMemoryDatabase(), "Mat,YM-001,desc,Sports,10.00,1,1,surprise\n")
    assert report.rows[0].outcome is RowOutcome.FAILED
    assert "expected 7 fields but found 8" in report.rows[0].messages[0]


async def test_a_file_with_only_invalid_rows_saves_nothing() -> None:
    database = InMemoryDatabase()
    report = await run(database, ",,,,,,\nX,???,,Nope,abc,1.5,heavy\n")
    assert report.summary[RowOutcome.FAILED] == 1
    assert report.rows[1].messages == (
        "sku: must contain only letters, digits and single hyphens, e.g. RS-001",
        "category: 'Nope' is not a known category",
        "price: 'abc' is not a valid decimal number",
        "stock: '1.5' is not a whole number",
        "weight_kg: 'heavy' is not a valid decimal number",
    )
    assert database.commits == 0


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"name,sku\nA,B\n", "Missing required columns: description, category, price"),
        (HEADER.encode(), "no data rows"),
        (b"\xff\xfe\x00n\x00a", "UTF-8"),
        (HEADER.replace("stock", "price").encode() + b"a,b,c,d,e,f,g\n", "Duplicated columns"),
        (HEADER.encode() + b'a,"unterminated\n', "Malformed CSV"),
    ],
)
async def test_rejects_unusable_files(content: bytes, message: str) -> None:
    with pytest.raises(InvalidImportFile, match=message):
        await importer(InMemoryDatabase()).execute(content)


async def test_enforces_the_row_limit() -> None:
    body = "".join(f"P{i},SKU-{i:03d},,Misc,1.00,1,0\n" for i in range(3))
    with pytest.raises(ImportLimitExceeded):
        await importer(InMemoryDatabase(), max_rows=2).execute((HEADER + body).encode())


def test_accepts_byte_order_marks_and_header_variants() -> None:
    table = CsvProductTableReader().read(
        (
            chr(0xFEFF)
            + "Name, SKU ,Description,Category,Price,Stock,Weight KG\r\nA,B,C,D,E,F,G\r\n"
        ).encode()
    )
    assert table.columns == (
        "name",
        "sku",
        "description",
        "category",
        "price",
        "stock",
        "weight_kg",
    )
    assert table.rows[0].line == 2


def test_number_parsers() -> None:
    assert str(parse_decimal(" .5 ")) == "0.5"
    assert parse_integer("+7") == 7
    with pytest.raises(InvalidValue, match="'1e3' is not a valid decimal number"):
        parse_decimal("1e3")
    with pytest.raises(InvalidValue, match=r"\.\.\.' is not a whole number"):
        parse_integer("9" * 50 + "x")
