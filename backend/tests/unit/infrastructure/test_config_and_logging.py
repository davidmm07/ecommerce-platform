import json
import logging
import sys

import pytest

from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.logging import JsonFormatter, RequestIdFilter, request_id_var
from ecommerce.infrastructure.persistence.read_models import escape_like, prefix_query


def test_settings_read_comma_separated_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://a.test, http://b.test,")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.max_request_bytes > settings.import_max_bytes


def test_settings_require_a_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="database_url"):
        Settings(_env_file=None)


def test_json_logs_carry_the_request_id_and_extras() -> None:
    record = logging.LogRecord("ecommerce", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.order_number = "ORD-1"
    token = request_id_var.set("req-12345678")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-12345678"
    assert payload["order_number"] == "ORD-1"


def test_json_logs_include_exceptions() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    assert "RuntimeError: boom" in json.loads(JsonFormatter().format(record))["exception"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Running shoes", "running:* & shoes:*"),
        ("usb-c 100W!", "usb:* & c:* & 100w:*"),
        ("!!! ???", None),
        ("foo_bar", "foo:* & bar:*"),
    ],
)
def test_prefix_queries_only_contain_safe_terms(text: str, expected: str | None) -> None:
    assert prefix_query(text) == expected


def test_like_patterns_are_escaped() -> None:
    assert escape_like(r"100%_off\now") == r"100\%\_off\\now"
