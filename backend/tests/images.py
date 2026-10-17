import io

from PIL import Image


def jpeg_bytes(
    width: int = 1600,
    height: int = 1200,
    *,
    color: tuple[int, int, int] = (200, 40, 40),
    orientation: int | None = None,
    with_gps: bool = False,
) -> bytes:
    image = Image.new("RGB", (width, height), color)
    image.paste((20, 20, 220), (0, 0, width // 2, height // 4))
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    if with_gps:
        exif[0x010F] = "Camera Maker"
        exif.get_ifd(0x8825)[2] = (40.0, 26.0, 46.0)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90, exif=exif.tobytes())
    return buffer.getvalue()


def png_bytes(width: int = 800, height: int = 800, *, transparent: bool = True) -> bytes:
    image = Image.new("RGBA", (width, height), (10, 120, 10, 0 if transparent else 255))
    image.paste((250, 250, 0, 255), (width // 4, height // 4, width // 2, height // 2))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
