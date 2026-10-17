import base64
import io

import pytest
from PIL import Image

from ecommerce.application.errors import ImageTooLarge, InvalidImage, UnsupportedImageType
from ecommerce.infrastructure.images.pillow_processor import PillowImageProcessor
from tests.images import jpeg_bytes, png_bytes


@pytest.fixture(scope="module")
def processor() -> PillowImageProcessor:
    return PillowImageProcessor(max_pixels=4_000_000)


def decode(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


async def test_creates_avif_and_webp_renditions_without_upscaling(
    processor: PillowImageProcessor,
) -> None:
    result = await processor.process(jpeg_bytes(1000, 750))

    assert result.widths == (160, 320, 640, 960, 1000)
    assert result.formats == ("avif", "webp")
    assert (result.width, result.height) == (1000, 750)
    assert len(result.variants) == 10
    by_key = {(variant.width, variant.format): variant for variant in result.variants}
    webp = decode(by_key[(640, "webp")].data)
    assert (webp.format, webp.size) == ("WEBP", (640, 480))
    assert decode(by_key[(320, "avif")].data).format == "AVIF"
    assert by_key[(160, "avif")].content_type == "image/avif"


async def test_caps_large_images_at_the_widest_rendition(processor: PillowImageProcessor) -> None:
    result = await processor.process(jpeg_bytes(2000, 1000))
    assert (result.width, result.height) == (1280, 640)
    assert result.widths[-1] == 1280


async def test_applies_the_exif_orientation_and_strips_metadata(
    processor: PillowImageProcessor,
) -> None:
    result = await processor.process(jpeg_bytes(1200, 800, orientation=6, with_gps=True))

    assert (result.width, result.height) == (800, 1200)
    for variant in result.variants:
        rendition = decode(variant.data)
        assert not rendition.getexif()
        assert "icc_profile" not in rendition.info


async def test_keeps_transparency_and_drops_useless_alpha(
    processor: PillowImageProcessor,
) -> None:
    transparent = await processor.process(png_bytes(transparent=True))
    opaque = await processor.process(png_bytes(transparent=False))
    assert decode(transparent.variants[1].data).mode == "RGBA"
    assert decode(opaque.variants[1].data).mode == "RGB"


async def test_builds_a_tiny_inline_placeholder(processor: PillowImageProcessor) -> None:
    result = await processor.process(jpeg_bytes(1600, 1200))
    prefix = "data:image/webp;base64,"
    assert result.placeholder.startswith(prefix)
    assert len(result.placeholder) < 1000
    tiny = decode(base64.b64decode(result.placeholder.removeprefix(prefix)))
    assert max(tiny.size) == 24


@pytest.mark.parametrize(
    "content",
    [
        b"definitely not an image",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"GIF89a" + b"\x00" * 64,
    ],
)
async def test_rejects_files_that_are_not_supported_images(
    processor: PillowImageProcessor, content: bytes
) -> None:
    with pytest.raises(UnsupportedImageType):
        await processor.process(content)


async def test_rejects_gif_images(processor: PillowImageProcessor) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 400), "red").save(buffer, "GIF")
    with pytest.raises(UnsupportedImageType):
        await processor.process(buffer.getvalue())


async def test_rejects_truncated_files(processor: PillowImageProcessor) -> None:
    content = jpeg_bytes(800, 600)
    with pytest.raises(InvalidImage):
        await processor.process(content[: len(content) // 2])


async def test_rejects_tiny_images(processor: PillowImageProcessor) -> None:
    with pytest.raises(InvalidImage, match="at least 200 pixels"):
        await processor.process(jpeg_bytes(150, 400))


async def test_rejects_images_with_too_many_pixels(processor: PillowImageProcessor) -> None:
    with pytest.raises(ImageTooLarge, match="4000000 pixels"):
        await processor.process(jpeg_bytes(2100, 2000))


def test_validates_the_output_formats() -> None:
    with pytest.raises(ValueError, match="heic"):
        PillowImageProcessor(formats=("heic",))
    with pytest.raises(RuntimeError):
        PillowImageProcessor(formats=())
