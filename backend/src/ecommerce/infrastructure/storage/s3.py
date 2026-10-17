import asyncio
from collections.abc import Collection
from typing import Any

import boto3

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
_DELETE_BATCH = 1000


class S3ObjectStorage:
    def __init__(self, *, client: Any, bucket: str, cache_control: str = IMMUTABLE_CACHE) -> None:
        self._client = client
        self._bucket = bucket
        self._cache_control = cache_control

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=self._cache_control,
        )

    async def delete(self, keys: Collection[str]) -> None:
        ordered = list(keys)
        for start in range(0, len(ordered), _DELETE_BATCH):
            batch = ordered[start : start + _DELETE_BATCH]
            await asyncio.to_thread(
                self._client.delete_objects,
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )


def create_s3_client(*, region: str, endpoint_url: str | None) -> Any:
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url)
