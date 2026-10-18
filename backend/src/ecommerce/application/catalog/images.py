import asyncio
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from ecommerce.application.catalog.use_cases import load_for_change
from ecommerce.application.errors import ApplicationError, ImageTooLarge, InvalidImage
from ecommerce.application.ports.media import (
    ImageProcessor,
    ObjectStorage,
    ProcessedImage,
    RemoteImageFetcher,
)
from ecommerce.application.ports.system import Clock
from ecommerce.application.ports.unit_of_work import UnitOfWorkFactory
from ecommerce.domain.catalog.image import ImageCredit, ProductImage, parse_web_url
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import DomainError, FieldErrors

HASH_LENGTH = 20

logger = logging.getLogger(__name__)


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:HASH_LENGTH]


@dataclass(frozen=True, slots=True)
class ReplaceProductImageCommand:
    product_id: UUID
    content: bytes = field(repr=False)
    expected_version: int | None = None
    origin_url: str | None = None
    credit: ImageCredit | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ImageCreditInput:
    author: str
    license: str
    source_url: str
    license_url: str | None = None


@dataclass(frozen=True, slots=True)
class ImportProductImageFromUrlCommand:
    product_id: UUID
    url: str
    credit: ImageCreditInput | None = None
    expected_version: int | None = None


@dataclass(frozen=True, slots=True)
class RemoveProductImageCommand:
    product_id: UUID
    expected_version: int | None = None


class ReplaceProductImage:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        processor: ImageProcessor,
        storage: ObjectStorage,
        clock: Clock,
        max_bytes: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._processor = processor
        self._storage = storage
        self._clock = clock
        self._max_bytes = max_bytes

    async def execute(self, command: ReplaceProductImageCommand) -> Product:
        self._check_size(command.content)
        async with self._uow_factory() as uow:
            current = await load_for_change(uow, command.product_id, command.expected_version)
        processed = await self._processor.process(command.content)
        image = _image_from(command, processed)
        reused = current.image is not None and current.image.key == image.key
        await _store(self._storage, image, processed)
        try:
            async with self._uow_factory() as uow:
                product = await load_for_change(uow, command.product_id, command.expected_version)
                previous = product.replace_image(image, self._clock.now())
                await uow.products.update(product)
                await uow.commit()
        except Exception:
            if not reused:
                await discard(self._storage, image)
            raise
        if previous is not None and previous.key != image.key:
            await discard(self._storage, previous)
        return product

    def _check_size(self, content: bytes) -> None:
        if not content:
            raise InvalidImage("The image file is empty")
        if len(content) > self._max_bytes:
            raise ImageTooLarge(f"The image must not exceed {self._max_bytes} bytes")


class RemoveProductImage:
    def __init__(
        self, *, uow_factory: UnitOfWorkFactory, storage: ObjectStorage, clock: Clock
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._clock = clock

    async def execute(self, command: RemoveProductImageCommand) -> Product:
        async with self._uow_factory() as uow:
            product = await load_for_change(uow, command.product_id, command.expected_version)
            previous = product.remove_image(self._clock.now())
            if previous is not None:
                await uow.products.update(product)
                await uow.commit()
        if previous is not None:
            await discard(self._storage, previous)
        return product


class ImportProductImageFromUrl:
    def __init__(self, *, fetcher: RemoteImageFetcher, replace_image: ReplaceProductImage) -> None:
        self._fetcher = fetcher
        self._replace_image = replace_image

    async def execute(self, command: ImportProductImageFromUrlCommand) -> Product:
        errors = FieldErrors()
        with errors.collect("url"):
            url = parse_web_url(command.url)
        with errors.collect("credit"):
            credit = _credit_from(command.credit)
        errors.raise_if_any()
        content = await self._fetcher.fetch(url)
        return await self._replace_image.execute(
            ReplaceProductImageCommand(
                command.product_id,
                content,
                expected_version=command.expected_version,
                origin_url=url,
                credit=credit,
            )
        )


class ImageImportOutcome(StrEnum):
    ATTACHED = "attached"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ImageSource:
    sku: str
    url: str
    credit: ImageCreditInput | None = None


@dataclass(frozen=True, slots=True)
class ImageImportResult:
    sku: str
    outcome: ImageImportOutcome
    message: str = ""


class ImportProductImages:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        import_from_url: ImportProductImageFromUrl,
        concurrency: int = 4,
    ) -> None:
        self._uow_factory = uow_factory
        self._import_from_url = import_from_url
        self._concurrency = concurrency

    async def execute(self, sources: Sequence[ImageSource]) -> list[ImageImportResult]:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def run(source: ImageSource) -> ImageImportResult:
            async with semaphore:
                return await self._import_one(source)

        return list(await asyncio.gather(*(run(source) for source in sources)))

    async def _import_one(self, source: ImageSource) -> ImageImportResult:
        try:
            sku = Sku.parse(source.sku)
            async with self._uow_factory() as uow:
                product = await uow.products.get_by_sku(sku)
            if product is None:
                return ImageImportResult(source.sku, ImageImportOutcome.FAILED, "no active product")
            if product.image is not None and product.image.origin_url == source.url.strip():
                return ImageImportResult(sku.value, ImageImportOutcome.UNCHANGED)
            await self._import_from_url.execute(
                ImportProductImageFromUrlCommand(product.id, source.url, source.credit)
            )
        except (ApplicationError, DomainError) as exc:
            return ImageImportResult(source.sku, ImageImportOutcome.FAILED, exc.message)
        return ImageImportResult(sku.value, ImageImportOutcome.ATTACHED)


def _credit_from(raw: ImageCreditInput | None) -> ImageCredit | None:
    if raw is None:
        return None
    return ImageCredit.build(
        author=raw.author,
        license=raw.license,
        source_url=raw.source_url,
        license_url=raw.license_url,
    )


def _image_from(command: ReplaceProductImageCommand, processed: ProcessedImage) -> ProductImage:
    return ProductImage(
        key=f"products/{command.product_id}/{content_hash(command.content)}",
        width=processed.width,
        height=processed.height,
        widths=processed.widths,
        formats=processed.formats,
        placeholder=processed.placeholder,
        origin_url=command.origin_url,
        credit=command.credit,
    )


async def _store(storage: ObjectStorage, image: ProductImage, processed: ProcessedImage) -> None:
    await asyncio.gather(
        *(
            storage.put(
                image.variant_key(variant.width, variant.format),
                variant.data,
                content_type=variant.content_type,
            )
            for variant in processed.variants
        )
    )


async def discard(storage: ObjectStorage, image: ProductImage) -> None:
    try:
        await storage.delete(image.variant_keys)
    except Exception:
        logger.warning("could not delete image variants", extra={"image_key": image.key})
