from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageVariant:
    width: int
    format: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    width: int
    height: int
    placeholder: str
    variants: tuple[ImageVariant, ...]

    @property
    def widths(self) -> tuple[int, ...]:
        return tuple(sorted({variant.width for variant in self.variants}))

    @property
    def formats(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(variant.format for variant in self.variants))


class ImageProcessor(Protocol):
    async def process(self, data: bytes) -> ProcessedImage: ...


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    async def delete(self, keys: Collection[str]) -> None: ...


class RemoteImageFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...
