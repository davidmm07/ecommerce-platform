from uuid import uuid4

import pytest

from ecommerce.application.catalog.images import (
    ImageImportOutcome,
    ImportProductImageFromUrl,
    ImportProductImages,
    ReplaceProductImage,
)
from ecommerce.application.errors import (
    ImageSourceUnavailable,
    ImportLimitExceeded,
    InvalidImportFile,
)
from ecommerce.application.imports.report import ImportReport, RowOutcome
from ecommerce.application.imports.row_parser import parse_decimal, parse_integer
from ecommerce.application.imports.use_case import ImportProducts
from ecommerce.domain.errors import InvalidValue
from ecommerce.infrastructure.files.csv_reader import CsvProductTableReader
from tests.conftest import SAMPLE_CSV, SAMPLE_IMAGES_CSV
from tests.factories import FixedClock, make_product
from tests.fakes import (
    FakeImageFetcher,
    FakeImageProcessor,
    InMemoryDatabase,
    InMemoryObjectStorage,
    InMemoryUnitOfWork,
)

HEADER = "name,sku,description,category,price,stock,weight_kg\n"
IMAGE_HEADER = (
    "name,sku,description,category,price,stock,weight_kg,"
    "image_url,image_author,image_license,image_license_url,image_source_url\n"
)


def importer(
    database: InMemoryDatabase,
    *,
    max_rows: int = 100,
    fetcher: FakeImageFetcher | None = None,
) -> ImportProducts:
    def uow_factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(database)

    replace_image = ReplaceProductImage(
        uow_factory=uow_factory,
        processor=FakeImageProcessor(),
        storage=InMemoryObjectStorage(),
        clock=FixedClock(),
        max_bytes=1024,
    )
    images = ImportProductImages(
        uow_factory=uow_factory,
        import_from_url=ImportProductImageFromUrl(
            fetcher=fetcher or FakeImageFetcher(), replace_image=replace_image
        ),
    )
    return ImportProducts(
        uow_factory=uow_factory,
        reader=CsvProductTableReader(),
        images=images,
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


async def test_imports_the_sample_file_with_image_columns() -> None:
    database = InMemoryDatabase()
    fetcher = FakeImageFetcher()
    plain = await importer(InMemoryDatabase()).execute(SAMPLE_CSV.read_bytes())
    report = await importer(database, fetcher=fetcher).execute(SAMPLE_IMAGES_CSV.read_bytes())

    assert report.summary == plain.summary
    assert [row.messages for row in report.rows] == [row.messages for row in plain.rows]
    assert report.image_summary == {
        ImageImportOutcome.ATTACHED: 83,
        ImageImportOutcome.UNCHANGED: 0,
        ImageImportOutcome.FAILED: 0,
    }
    assert len(fetcher.requested) == 83
    products = list(database.products.values())
    assert all(product.image is not None for product in products)
    shoes = next(product for product in products if product.sku.value == "RS-001")
    assert shoes.image is not None
    assert shoes.image.credit is not None
    assert shoes.image.origin_url == next(
        row.get("image_url")
        for row in CsvProductTableReader().read(SAMPLE_IMAGES_CSV.read_bytes()).rows
        if row.line == 36
    )

    again = await importer(database, fetcher=fetcher).execute(SAMPLE_IMAGES_CSV.read_bytes())
    assert again.summary[RowOutcome.UNCHANGED] == 83
    assert again.image_summary[ImageImportOutcome.UNCHANGED] == 83
    assert len(fetcher.requested) == 83


async def test_image_downloads_never_undo_saved_products() -> None:
    database = InMemoryDatabase()
    fetcher = FakeImageFetcher(
        {"https://img.example.com/gone.jpg": ImageSourceUnavailable("The image URL answered 404")}
    )
    body = (
        IMAGE_HEADER + "Mat,YM-001,,Sports,10.00,1,1,https://img.example.com/mat.jpg,"
        "Jane Doe,CC BY 2.0,,https://example.com/mat\n"
        + "Cup,CU-001,,Kitchen,5.00,1,0.2,https://img.example.com/gone.jpg,,,,\n"
        + "Pen,PN-001,,Stationery,2.00,1,0.1,,,,,\n"
    )
    report = await importer(database, fetcher=fetcher).execute(body.encode())

    assert [(row.outcome, row.image, row.messages) for row in report.rows] == [
        (RowOutcome.CREATED, ImageImportOutcome.ATTACHED, ()),
        (RowOutcome.CREATED, ImageImportOutcome.FAILED, ("image: The image URL answered 404",)),
        (RowOutcome.CREATED, None, ()),
    ]
    assert len(database.products) == 3


async def test_validates_image_columns_with_the_row() -> None:
    database = InMemoryDatabase()
    fetcher = FakeImageFetcher()
    body = (
        IMAGE_HEADER
        + "Mat,YM-001,,Sports,10.00,1,1,ftp://img.example.com/mat.jpg,,,,\n"
        + "Cup,CU-001,,Kitchen,5.00,1,0.2,,Jane Doe,,,\n"
        + "Pen,PN-001,,Stationery,2.00,1,0.1,https://img.example.com/pen.jpg,"
        "Jane Doe,,,javascript:alert(1)\n"
    )
    report = await importer(database, fetcher=fetcher).execute(body.encode())

    assert [(row.outcome, row.messages) for row in report.rows] == [
        (RowOutcome.FAILED, ("image_url: must be an http or https URL",)),
        (RowOutcome.FAILED, ("image_url: is required when a photo credit is given",)),
        (
            RowOutcome.FAILED,
            (
                "image_license: is required",
                "image_source_url: must be an http or https URL",
            ),
        ),
    ]
    assert database.products == {}
    assert fetcher.requested == []


async def test_dry_runs_validate_image_columns_without_downloading() -> None:
    database = InMemoryDatabase()
    fetcher = FakeImageFetcher()
    body = IMAGE_HEADER + "Mat,YM-001,,Sports,10.00,1,1,https://img.example.com/mat.jpg,,,,\n"
    report = await importer(database, fetcher=fetcher).execute(body.encode(), dry_run=True)

    assert (report.rows[0].outcome, report.rows[0].image) == (RowOutcome.CREATED, None)
    assert fetcher.requested == []


async def test_a_different_image_makes_a_repeated_row_a_new_version() -> None:
    body = (
        IMAGE_HEADER
        + "Mat,YM-001,,Sports,10.00,1,1,https://img.example.com/a.jpg,,,,\n"
        + "Mat,YM-001,,Sports,10.00,1,1,https://img.example.com/b.jpg,,,,\n"
        + "Mat,YM-001,,Sports,10.00,1,1,https://img.example.com/b.jpg,,,,\n"
    )
    report = await importer(InMemoryDatabase()).execute(body.encode())
    assert outcomes(report) == {
        2: (RowOutcome.SKIPPED, ("superseded by line 3, which has the same SKU",)),
        3: (RowOutcome.CREATED, ()),
        4: (RowOutcome.SKIPPED, ("exact duplicate of line 3",)),
    }
