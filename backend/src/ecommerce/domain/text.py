import re
import unicodedata

from ecommerce.domain.errors import InvalidValue

_MARKUP = re.compile(r"<\s*/?\s*[A-Za-z!][^>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def single_line(value: str, *, max_length: int, required: bool = True) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    return _guard(text, max_length=max_length, required=required)


def multi_line(value: str, *, max_length: int, required: bool = False) -> str:
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").strip()
    return _guard(text, max_length=max_length, required=required)


def _guard(text: str, *, max_length: int, required: bool) -> str:
    if required and not text:
        raise InvalidValue("is required")
    if len(text) > max_length:
        raise InvalidValue(f"must be at most {max_length} characters")
    if _CONTROL.search(text):
        raise InvalidValue("must not contain control characters")
    if _MARKUP.search(text):
        raise InvalidValue("must be plain text without HTML markup")
    return text
