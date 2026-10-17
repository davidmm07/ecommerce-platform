import json
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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


@pytest.fixture
def image_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = tmp_path_factory.mktemp("remote-images")
    (root / "shoes.jpg").write_bytes(jpeg_bytes(900, 600))
    (root / "speaker.png").write_bytes(png_bytes())
    (root / "notes.txt").write_text("not an image")
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def write_manifest(path: Path, rows: list[str]) -> Path:
    header = "sku,image_url,author,license,license_url,source_url"
    path.write_text("\n".join([header, *rows]) + "\n")
    return path


def test_import_images_downloads_sources_from_a_manifest(
    cli_env: None,
    image_server: str,
    tmp_path: Path,
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_IMAGE_FETCH_ALLOW_HTTP", "true")
    monkeypatch.setenv("APP_IMAGE_FETCH_ALLOW_PRIVATE_NETWORKS", "true")
    assert main(["import-products", str(SAMPLE_CSV)]) == 0
    capsys.readouterr()
    manifest = write_manifest(
        tmp_path / "images.csv",
        [
            f"RS-001,{image_server}/shoes.jpg,Jane Doe,CC BY 2.0,,https://example.com/shoes",
            f"bs-021,{image_server}/speaker.png,,,,",
            f"NOPE-999,{image_server}/shoes.jpg,,,,",
            f"TM-029,{image_server}/notes.txt,,,,",
        ],
    )

    assert main(["import-images", str(manifest)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["import-images", str(manifest), "--strict"]) == 1
    second = json.loads(capsys.readouterr().out)

    assert (first["total"], first["attached"], first["not_found"], first["failed"]) == (
        4,
        2,
        1,
        1,
    )
    assert (second["attached"], second["unchanged"]) == (0, 2)
    assert any((media_root / "products").rglob("*-640.avif"))


def test_import_images_blocks_private_addresses_by_default(
    cli_env: None, image_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import-products", str(SAMPLE_CSV)]) == 0
    capsys.readouterr()
    manifest = write_manifest(tmp_path / "images.csv", [f"RS-001,{image_server}/shoes.jpg,,,,"])
    assert main(["import-images", str(manifest)]) == 0
    [issue] = json.loads(capsys.readouterr().out)["issues"]
    assert issue["message"] == "The image URL must use https"


def test_import_images_rejects_unusable_manifests(
    cli_env: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.csv"
    broken.write_text("sku,url\nRS-001,https://example.com/a.jpg\n")
    assert main(["import-images", str(broken)]) == 1
    assert main(["import-images", str(tmp_path / "missing.csv")]) == 1
    assert "import failed" in capsys.readouterr().err
