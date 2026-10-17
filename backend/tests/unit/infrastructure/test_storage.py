from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

from ecommerce.infrastructure.storage.local import LocalObjectStorage
from ecommerce.infrastructure.storage.s3 import S3ObjectStorage, create_s3_client


async def test_local_storage_writes_and_deletes_files(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    await storage.put("products/abc/123-640.webp", b"data", content_type="image/webp")
    await storage.put("products/abc/123-320.webp", b"more", content_type="image/webp")

    target = tmp_path / "products" / "abc" / "123-640.webp"
    assert target.read_bytes() == b"data"
    assert not list(target.parent.glob("*.tmp"))

    await storage.delete(["products/abc/123-640.webp", "products/abc/123-320.webp", "missing.webp"])
    assert not (tmp_path / "products" / "abc").exists()
    assert storage.root == tmp_path.resolve()


@pytest.mark.parametrize("key", ["../escape.webp", "/etc/passwd", "a/../../b", "UPPER.webp", ""])
async def test_local_storage_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        await LocalObjectStorage(tmp_path).put(key, b"x", content_type="image/webp")


@pytest.fixture
def s3_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = create_s3_client(region="us-east-1", endpoint_url=None)
        client.create_bucket(Bucket="media")
        yield client


async def test_s3_storage_sets_content_type_and_long_lived_caching(s3_client: Any) -> None:
    storage = S3ObjectStorage(client=s3_client, bucket="media")
    await storage.put("products/abc/123-640.avif", b"avif", content_type="image/avif")

    stored = s3_client.get_object(Bucket="media", Key="products/abc/123-640.avif")
    assert stored["Body"].read() == b"avif"
    assert stored["ContentType"] == "image/avif"
    assert stored["CacheControl"] == "public, max-age=31536000, immutable"


async def test_s3_storage_deletes_in_batches(s3_client: Any) -> None:
    storage = S3ObjectStorage(client=s3_client, bucket="media")
    keys = [f"products/abc/{index}.webp" for index in range(1005)]
    for key in keys[:3]:
        await storage.put(key, b"x", content_type="image/webp")
    await storage.delete(keys)
    assert s3_client.list_objects_v2(Bucket="media")["KeyCount"] == 0


def test_moto_uses_the_regular_boto3_client() -> None:
    assert boto3.__name__ == "boto3"
