import asyncio
import base64
import io
import warnings
from collections.abc import Sequence

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError, features

from ecommerce.application.errors import ImageTooLarge, InvalidImage, UnsupportedImageType
from ecommerce.application.ports.media import ImageVariant, ProcessedImage
from ecommerce.domain.catalog.image import IMAGE_FORMATS

DEFAULT_WIDTHS = (160, 320, 640, 960, 1280)
ACCEPTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "AVIF"})
CONTENT_TYPES = {"avif": "image/avif", "webp": "image/webp"}
PLACEHOLDER_SIZE = 24
_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))


class PillowImageProcessor:
    def __init__(
        self,
        *,
        widths: Sequence[int] = DEFAULT_WIDTHS,
        formats: Sequence[str] = IMAGE_FORMATS,
        max_pixels: int = 40_000_000,
        min_side: int = 200,
        max_concurrency: int = 2,
        avif_quality: int = 55,
        webp_quality: int = 80,
    ) -> None:
        self._widths = tuple(sorted(set(widths)))
        unknown = sorted(set(formats) - set(CONTENT_TYPES))
        if unknown:
            raise ValueError(f"Unsupported output formats: {', '.join(unknown)}")
        self._formats = tuple(fmt for fmt in formats if features.check(fmt))
        if not self._formats:
            raise RuntimeError("Pillow was built without AVIF and WebP support")
        self._max_pixels = max_pixels
        self._min_side = min_side
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._quality = {"avif": avif_quality, "webp": webp_quality}

    @property
    def formats(self) -> tuple[str, ...]:
        return self._formats

    async def process(self, data: bytes) -> ProcessedImage:
        async with self._semaphore:
            return await asyncio.to_thread(self._process, data)

    def _process(self, data: bytes) -> ProcessedImage:
        image = _normalize(self._open(data))
        width, height = image.size
        if min(width, height) < self._min_side:
            raise InvalidImage(f"The image must be at least {self._min_side} pixels on each side")
        widths = self._widths_for(width)
        variants: list[ImageVariant] = []
        for target in widths:
            resized = image if target == width else _resize(image, target)
            variants.extend(
                ImageVariant(target, fmt, CONTENT_TYPES[fmt], self._encode(resized, fmt))
                for fmt in self._formats
            )
        largest = widths[-1]
        return ProcessedImage(
            width=largest,
            height=max(1, round(height * largest / width)),
            placeholder=_placeholder(image),
            variants=tuple(variants),
        )

    def _open(self, data: bytes) -> Image.Image:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as probe:
                    if probe.format not in ACCEPTED_FORMATS:
                        raise UnsupportedImageType(_unsupported_message())
                    if probe.width * probe.height > self._max_pixels:
                        raise ImageTooLarge(f"The image must not exceed {self._max_pixels} pixels")
                    probe.verify()
                image = Image.open(io.BytesIO(data))
                image.load()
        except UnidentifiedImageError as exc:
            raise UnsupportedImageType(_unsupported_message()) from exc
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageTooLarge(f"The image must not exceed {self._max_pixels} pixels") from exc
        except (OSError, SyntaxError, ValueError) as exc:
            raise InvalidImage("The image file is corrupted or truncated") from exc
        return image

    def _widths_for(self, width: int) -> tuple[int, ...]:
        largest = min(width, self._widths[-1])
        return tuple(sorted({w for w in self._widths if w < largest} | {largest}))

    def _encode(self, image: Image.Image, fmt: str) -> bytes:
        buffer = io.BytesIO()
        if fmt == "avif":
            image.save(buffer, "AVIF", quality=self._quality["avif"], speed=6)
        else:
            image.save(buffer, "WEBP", quality=self._quality["webp"], method=5)
        return buffer.getvalue()


def _normalize(image: Image.Image) -> Image.Image:
    oriented = ImageOps.exif_transpose(image)
    oriented = _to_srgb(oriented)
    has_alpha = oriented.mode in {"RGBA", "LA", "PA"} or (
        oriented.mode == "P" and "transparency" in oriented.info
    )
    normalized = oriented.convert("RGBA" if has_alpha else "RGB")
    if has_alpha and normalized.getchannel("A").getextrema() == (255, 255):
        normalized = normalized.convert("RGB")
    normalized.info = {}
    return normalized


def _to_srgb(image: Image.Image) -> Image.Image:
    icc = image.info.get("icc_profile")
    if not icc or image.mode not in {"RGB", "RGBA", "CMYK"}:
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        output = "RGBA" if image.mode == "RGBA" else "RGB"
        converted = ImageCms.profileToProfile(image, source, _SRGB, outputMode=output)
    except (ImageCms.PyCMSError, OSError):
        return image
    return converted if converted is not None else image


def _resize(image: Image.Image, width: int) -> Image.Image:
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS, reducing_gap=3.0)


def _placeholder(image: Image.Image) -> str:
    tiny = image.copy()
    tiny.thumbnail((PLACEHOLDER_SIZE, PLACEHOLDER_SIZE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    tiny.save(buffer, "WEBP", quality=40)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _unsupported_message() -> str:
    return "Upload a JPEG, PNG, WebP or AVIF image"
