import re
import unicodedata

from ecommerce.domain.errors import InvalidValue

_MARKUP = re.compile(r"<\s*/?\s*[A-Za-z!][^>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SQL_PAYLOADS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:drop|truncate|alter)\s+(?:table|database|schema|view|index)\b",
        r"\bdelete\s+from\b",
        r"\binsert\s+into\b",
        r"\bunion\s+(?:all\s+)?select\b",
        r"\bupdate\s+\w+\s+set\s+\w+\s*=",
        r"\b(?:exec|execute)\s*\(",
        r"['\"]\s*\)*\s*(?:or|and)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+",
        r";\s*--|['\")]\s*--",
        r"/\*|\*/",
        r"\b(?:xp_cmdshell|pg_sleep|waitfor\s+delay)\b",
    )
)


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


def reject_sql_payload(text: str) -> str:
    if any(pattern.search(text) for pattern in _SQL_PAYLOADS):
        raise InvalidValue("looks like an SQL injection payload, use plain product text")
    return text
