import json
from pathlib import Path

import pytest

from ecommerce.cli import main
from ecommerce.container import Container
from tests.conftest import SAMPLE_CSV


@pytest.fixture
def cli_env(clean_database: Container, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", clean_database.settings.database_url)
    monkeypatch.setenv("APP_LOG_FORMAT", "text")


def test_dry_run_import_prints_a_summary(cli_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["import-products", str(SAMPLE_CSV), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert (summary["dry_run"], summary["created"], summary["failed"]) == (True, 84, 8)
    assert {issue["line"] for issue in summary["issues"]} >= {7, 16, 20, 62}


def test_reports_unusable_files(
    cli_env: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    assert main(["import-products", str(empty)]) == 1
    assert main(["import-products", str(tmp_path / "missing.csv")]) == 1
    assert "import failed" in capsys.readouterr().err
