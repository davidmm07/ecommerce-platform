import json
from pathlib import Path

import pytest

from ecommerce.cli import main
from ecommerce.container import Container
from tests.conftest import SAMPLE_CSV
from tests.images import jpeg_bytes, png_bytes


@pytest.fixture
def cli_env(clean_database: Container, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", clean_database.settings.database_url)
    monkeypatch.setenv("APP_LOG_FORMAT", "text")
    monkeypatch.setenv("APP_MEDIA_ROOT", str(clean_database.settings.media_root))


def test_dry_run_import_prints_a_summary(cli_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["import-products", str(SAMPLE_CSV), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert (summary["dry_run"], summary["created"], summary["failed"]) == (True, 83, 9)
    assert {issue["line"] for issue in summary["issues"]} >= {7, 16, 20, 62}


def test_reports_unusable_files(
    cli_env: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    assert main(["import-products", str(empty)]) == 1
    assert main(["import-products", str(tmp_path / "missing.csv")]) == 1
    assert "import failed" in capsys.readouterr().err


def test_import_images_attaches_files_named_after_skus(
    cli_env: None, tmp_path: Path, media_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import-products", str(SAMPLE_CSV)]) == 0
    capsys.readouterr()
    (tmp_path / "RS-001.jpg").write_bytes(jpeg_bytes(900, 600))
    (tmp_path / "bs-021.png").write_bytes(png_bytes())
    (tmp_path / "NOPE-999.jpg").write_bytes(jpeg_bytes(400, 400))
    (tmp_path / "notes.txt").write_text("ignored")

    assert main(["import-images", str(tmp_path)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["import-images", str(tmp_path)]) == 0
    second = json.loads(capsys.readouterr().out)

    assert (first["total_files"], first["attached"], first["not_found"]) == (3, 2, 1)
    assert (second["attached"], second["unchanged"]) == (0, 2)
    assert any((media_root / "products").rglob("*-640.avif"))


def test_import_images_fails_on_invalid_files(
    cli_env: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import-products", str(SAMPLE_CSV)]) == 0
    (tmp_path / "RS-001.jpg").write_bytes(b"not an image")
    assert main(["import-images", str(tmp_path)]) == 1
    assert main(["import-images", str(tmp_path / "missing")]) == 1
    assert "import failed" in capsys.readouterr().err
