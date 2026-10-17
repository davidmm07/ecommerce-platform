import pytest

from ecommerce.application.catalog.images import (
    ImageCreditInput,
    ImageImportOutcome,
    ImageSource,
    ImportProductImageFromUrl,
    ImportProductImageFromUrlCommand,
    ImportProductImages,
    RemoveProductImage,
    RemoveProductImageCommand,
    ReplaceProductImage,
    ReplaceProductImageCommand,
    content_hash,
)
from ecommerce.application.errors import (
    ImageSourceUnavailable,
    ImageTooLarge,
    InvalidImage,
    UnsupportedImageType,
    VersionMismatch,
)
from ecommerce.application.ports.media import ProcessedImage
from ecommerce.domain.errors import DomainValidationError
from tests.factories import FixedClock, make_product
from tests.fakes import (
    FakeImageFetcher,
    FakeImageProcessor,
    InMemoryDatabase,
    InMemoryObjectStorage,
    InMemoryUnitOfWork,
)

CONTENT = b"\xff\xd8 fake jpeg bytes"


def replace_use_case(
    database: InMemoryDatabase,
    storage: InMemoryObjectStorage,
    processor: FakeImageProcessor | None = None,
    *,
    max_bytes: int = 1024,
) -> ReplaceProductImage:
    return ReplaceProductImage(
        uow_factory=lambda: InMemoryUnitOfWork(database),
        processor=processor or FakeImageProcessor(),
        storage=storage,
        clock=FixedClock(),
        max_bytes=max_bytes,
    )


@pytest.fixture
def database() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture
def storage() -> InMemoryObjectStorage:
    return InMemoryObjectStorage()


async def test_stores_every_variant_and_attaches_the_image(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)

    updated = await replace_use_case(database, storage).execute(
        ReplaceProductImageCommand(product.id, CONTENT, expected_version=1)
    )

    image = updated.image
    assert image is not None
    assert image.key == f"products/{product.id}/{content_hash(CONTENT)}"
    assert (image.widths, image.formats) == ((320, 640), ("avif", "webp"))
    assert set(storage.objects) == set(image.variant_keys)
    assert storage.objects[image.variant_key(640, "avif")][1] == "image/avif"
    assert database.product(product.id).image == image
    assert updated.version == 2


async def test_replacing_deletes_the_previous_variants(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    use_case = replace_use_case(database, storage)
    first = await use_case.execute(ReplaceProductImageCommand(product.id, CONTENT))
    second = await use_case.execute(ReplaceProductImageCommand(product.id, b"other image"))

    assert first.image is not None
    assert second.image is not None
    assert set(storage.objects) == set(second.image.variant_keys)


async def test_uploading_the_same_file_twice_keeps_its_variants(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    use_case = replace_use_case(database, storage)
    await use_case.execute(ReplaceProductImageCommand(product.id, CONTENT))
    again = await use_case.execute(ReplaceProductImageCommand(product.id, CONTENT))
    assert again.image is not None
    assert set(storage.objects) == set(again.image.variant_keys)


async def test_a_failed_update_discards_the_new_variants(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)

    class MovingTarget(FakeImageProcessor):
        async def process(self, data: bytes) -> ProcessedImage:
            database.product(product.id).version = 5
            return await super().process(data)

    with pytest.raises(VersionMismatch):
        await replace_use_case(database, storage, MovingTarget()).execute(
            ReplaceProductImageCommand(product.id, CONTENT, expected_version=1)
        )
    assert storage.objects == {}


@pytest.mark.parametrize(
    ("content", "error"),
    [(b"", InvalidImage), (b"x" * 2048, ImageTooLarge)],
)
async def test_rejects_empty_and_oversized_files_before_processing(
    database: InMemoryDatabase,
    storage: InMemoryObjectStorage,
    content: bytes,
    error: type[Exception],
) -> None:
    product = make_product()
    database.seed(product)
    processor = FakeImageProcessor()
    with pytest.raises(error):
        await replace_use_case(database, storage, processor).execute(
            ReplaceProductImageCommand(product.id, content)
        )
    assert processor.calls == 0


async def test_stale_versions_are_rejected_before_processing(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    processor = FakeImageProcessor()
    with pytest.raises(VersionMismatch):
        await replace_use_case(database, storage, processor).execute(
            ReplaceProductImageCommand(product.id, CONTENT, expected_version=9)
        )
    assert processor.calls == 0


async def test_remove_detaches_and_deletes_variants(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    await replace_use_case(database, storage).execute(
        ReplaceProductImageCommand(product.id, CONTENT)
    )
    remove = RemoveProductImage(
        uow_factory=lambda: InMemoryUnitOfWork(database), storage=storage, clock=FixedClock()
    )

    updated = await remove.execute(RemoveProductImageCommand(product.id))
    assert updated.image is None
    assert storage.objects == {}
    commits = database.commits
    await remove.execute(RemoveProductImageCommand(product.id))
    assert database.commits == commits


async def test_storage_failures_on_cleanup_do_not_fail_the_request(
    database: InMemoryDatabase,
) -> None:
    product = make_product()
    database.seed(product)
    storage = InMemoryObjectStorage()
    use_case = replace_use_case(database, storage)
    await use_case.execute(ReplaceProductImageCommand(product.id, CONTENT))
    storage.fail_deletes = True
    updated = await use_case.execute(ReplaceProductImageCommand(product.id, b"newer"))
    assert updated.image is not None


def url_importer(
    database: InMemoryDatabase,
    storage: InMemoryObjectStorage,
    fetcher: FakeImageFetcher,
    processor: FakeImageProcessor | None = None,
) -> ImportProductImageFromUrl:
    return ImportProductImageFromUrl(
        fetcher=fetcher, replace_image=replace_use_case(database, storage, processor)
    )


CREDIT = ImageCreditInput(
    author="Jane Doe",
    license="CC BY 2.0",
    source_url="https://www.flickr.com/photos/example/1",
    license_url="https://creativecommons.org/licenses/by/2.0/",
)


async def test_import_from_url_stores_origin_and_credit(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    fetcher = FakeImageFetcher()

    updated = await url_importer(database, storage, fetcher).execute(
        ImportProductImageFromUrlCommand(product.id, " https://img.example.com/a.jpg ", CREDIT)
    )

    assert fetcher.requested == ["https://img.example.com/a.jpg"]
    assert updated.image is not None
    assert updated.image.origin_url == "https://img.example.com/a.jpg"
    assert updated.image.credit is not None
    assert updated.image.credit.author == "Jane Doe"


async def test_import_from_url_validates_before_downloading(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    product = make_product()
    database.seed(product)
    fetcher = FakeImageFetcher()
    bad_credit = ImageCreditInput(author="", license="CC BY", source_url="javascript:alert(1)")

    with pytest.raises(DomainValidationError) as caught:
        await url_importer(database, storage, fetcher).execute(
            ImportProductImageFromUrlCommand(product.id, "ftp://img.example.com/a.jpg", bad_credit)
        )

    assert {error.field for error in caught.value.errors} == {
        "url",
        "credit.author",
        "credit.source_url",
    }
    assert fetcher.requested == []


async def test_bulk_import_reports_each_source(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    database.seed(make_product("RS-001"), make_product("BS-021"), make_product("TM-029"))
    fetcher = FakeImageFetcher(
        {"https://img.example.com/down.jpg": ImageSourceUnavailable("answered 404")}
    )
    importer = ImportProductImages(
        uow_factory=lambda: InMemoryUnitOfWork(database),
        import_from_url=url_importer(database, storage, fetcher),
    )
    sources = [
        ImageSource("rs-001", "https://img.example.com/shoes.jpg", CREDIT),
        ImageSource("NOPE-404", "https://img.example.com/x.jpg"),
        ImageSource("bad sku!", "https://img.example.com/y.jpg"),
        ImageSource("BS-021", "https://img.example.com/down.jpg"),
    ]

    first = await importer.execute(sources)
    second = await importer.execute(sources[:1])

    assert [(r.sku, r.outcome) for r in first] == [
        ("RS-001", ImageImportOutcome.ATTACHED),
        ("NOPE-404", ImageImportOutcome.NOT_FOUND),
        ("bad sku!", ImageImportOutcome.FAILED),
        ("BS-021", ImageImportOutcome.FAILED),
    ]
    assert first[3].message == "answered 404"
    assert second[0].outcome is ImageImportOutcome.UNCHANGED
    assert fetcher.requested.count("https://img.example.com/shoes.jpg") == 1


async def test_bulk_import_reports_processing_errors(
    database: InMemoryDatabase, storage: InMemoryObjectStorage
) -> None:
    database.seed(make_product("RS-001"))
    importer = ImportProductImages(
        uow_factory=lambda: InMemoryUnitOfWork(database),
        import_from_url=url_importer(
            database,
            storage,
            FakeImageFetcher(),
            FakeImageProcessor(error=UnsupportedImageType("not an image")),
        ),
    )
    [result] = await importer.execute([ImageSource("RS-001", "https://img.example.com/a.jpg")])
    assert (result.outcome, result.message) == (ImageImportOutcome.FAILED, "not an image")
