import asyncio
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from ecommerce.application.catalog.use_cases import load_for_change
from ecommerce.application.errors import ApplicationError, ImageTooLarge, InvalidImage
from ecommerce.application.ports.media import ImageProcessor, ObjectStorage, ProcessedImage
from ecommerce.application.ports.system import Clock
from ecommerce.application.ports.unit_of_work import UnitOfWorkFactory
from ecommerce.domain.catalog.image import ProductImage
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.errors import DomainError

HASH_LENGTH = 20

logger = logging.getLogger(__name__)


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:HASH_LENGTH]


@dataclass(frozen=True, slots=True)
class ReplaceProductImageCommand:
    product_id: UUID
    content: bytes = field(repr=False)
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
        image = _image_from(command.product_id, command.content, processed)
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


class ImageImportOutcome(StrEnum):
    ATTACHED = "attached"
    UNCHANGED = "unchanged"
    NOT_FOUND = "not_found"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ImageFile:
    sku: str
    content: bytes = field(repr=False)


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
        replace_image: ReplaceProductImage,
        concurrency: int = 4,
    ) -> None:
        self._uow_factory = uow_factory
        self._replace_image = replace_image
        self._concurrency = concurrency

    async def execute(self, files: Sequence[ImageFile]) -> list[ImageImportResult]:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def run(file: ImageFile) -> ImageImportResult:
            async with semaphore:
                return await self._import_one(file)

        return list(await asyncio.gather(*(run(file) for file in files)))

    async def _import_one(self, file: ImageFile) -> ImageImportResult:
        try:
            sku = Sku.parse(file.sku)
            async with self._uow_factory() as uow:
                product = await uow.products.get_by_sku(sku)
            if product is None:
                return ImageImportResult(
                    file.sku, ImageImportOutcome.NOT_FOUND, "no active product"
                )
            if product.image is not None and product.image.content_hash == content_hash(
                file.content
            ):
                return ImageImportResult(sku.value, ImageImportOutcome.UNCHANGED)
            await self._replace_image.execute(ReplaceProductImageCommand(product.id, file.content))
        except (ApplicationError, DomainError) as exc:
            return ImageImportResult(file.sku, ImageImportOutcome.FAILED, exc.message)
        return ImageImportResult(sku.value, ImageImportOutcome.ATTACHED)


def _image_from(product_id: UUID, content: bytes, processed: ProcessedImage) -> ProductImage:
    return ProductImage(
        key=f"products/{product_id}/{content_hash(content)}",
        width=processed.width,
        height=processed.height,
        widths=processed.widths,
        formats=processed.formats,
        placeholder=processed.placeholder,
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
