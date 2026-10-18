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


def write_products(path: Path, rows: list[str]) -> Path:
    header = (
        "name,sku,description,category,price,stock,weight_kg,"
        "image_url,image_author,image_license,image_license_url,image_source_url"
    )
    path.write_text("\n".join([header, *rows]) + "\n")
    return path


def test_import_products_downloads_images_from_image_columns(
    cli_env: None,
    image_server: str,
    tmp_path: Path,
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APP_IMAGE_FETCH_ALLOW_HTTP", "true")
    monkeypatch.setenv("APP_IMAGE_FETCH_ALLOW_PRIVATE_NETWORKS", "true")
    products = write_products(
        tmp_path / "products.csv",
        [
            f"Running Shoes,RS-001,,Footwear,89.99,10,0.35,{image_server}/shoes.jpg,"
            "Jane Doe,CC BY 2.0,,https://example.com/shoes",
            f"Speaker,BS-021,,Electronics,59.99,5,0.8,{image_server}/speaker.png,,,,",
            f"Notebook,TM-029,,Stationery,4.99,50,0.2,{image_server}/notes.txt,,,,",
            "Mug,MG-001,,Kitchen,9.99,20,0.3,,,,,",
        ],
    )

    assert main(["import-products", str(products)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["import-products", str(products)]) == 0
    second = json.loads(capsys.readouterr().out)

    assert (first["created"], first["images"]) == (
        4,
        {"attached": 2, "unchanged": 0, "failed": 1},
    )
    [issue] = first["issues"]
    assert (issue["sku"], issue["outcome"], issue["image"]) == ("TM-029", "created", "failed")
    assert (second["unchanged"], second["images"]["unchanged"]) == (4, 2)
    assert any((media_root / "products").rglob("*-640.avif"))


def test_import_products_blocks_private_image_addresses_by_default(
    cli_env: None, image_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    products = write_products(
        tmp_path / "products.csv",
        [f"Running Shoes,RS-001,,Footwear,89.99,10,0.35,{image_server}/shoes.jpg,,,,"],
    )
    assert main(["import-products", str(products)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["created"] == 1
    [issue] = summary["issues"]
    assert issue["messages"] == ["image: The image URL must use https"]
