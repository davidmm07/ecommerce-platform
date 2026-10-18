from collections.abc import Callable
from typing import Any

import httpx
import pytest

from ecommerce.application.errors import (
    ImageSourceUnavailable,
    ImageTooLarge,
    InvalidImageSource,
    UnsupportedImageType,
)
from ecommerce.infrastructure.images.remote_fetcher import HttpImageFetcher

PUBLIC = "93.184.216.34"
ADDRESSES = {
    "img.example.com": [PUBLIC],
    "cdn.example.com": [PUBLIC],
    "internal.example.com": ["10.0.0.7"],
    "metadata.example.com": ["169.254.169.254"],
    "loopback.example.com": ["127.0.0.1"],
    "ipv6.example.com": ["::1"],
    "mixed.example.com": [PUBLIC, "192.168.1.10"],
}


async def resolver(host: str) -> list[str]:
    return ADDRESSES[host]


class RecordedSleeps(list[float]):
    async def __call__(self, seconds: float) -> None:
        self.append(seconds)


def fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
    sleeps: RecordedSleeps | None = None,
    **options: Any,
) -> HttpImageFetcher:
    return HttpImageFetcher(
        max_bytes=1024,
        resolver=resolver,
        transport=httpx.MockTransport(handler),
        sleep=RecordedSleeps() if sleeps is None else sleeps,
        **options,
    )


def image_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpeg-bytes")


async def test_downloads_images_from_public_hosts() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return image_response(request)

    assert await fetcher(handler).fetch("https://img.example.com/a.jpg") == b"jpeg-bytes"
    assert seen[0].headers["user-agent"].startswith("EcommercePlatform")


@pytest.mark.parametrize(
    "url",
    [
        "https://internal.example.com/a.jpg",
        "https://metadata.example.com/latest/meta-data",
        "https://loopback.example.com/a.jpg",
        "https://ipv6.example.com/a.jpg",
        "https://mixed.example.com/a.jpg",
    ],
)
async def test_blocks_private_and_reserved_addresses(url: str) -> None:
    with pytest.raises(InvalidImageSource, match="private or reserved"):
        await fetcher(image_response).fetch(url)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://img.example.com/a.jpg", "must use https"),
        ("https://user:pass@img.example.com/a.jpg", "no credentials"),
        ("https://img.example.com:8443/a.jpg", "default port"),
    ],
)
async def test_rejects_unsafe_urls(url: str, message: str) -> None:
    with pytest.raises(InvalidImageSource, match=message):
        await fetcher(image_response).fetch(url)


async def test_allow_lists_and_development_switches() -> None:
    restricted = fetcher(image_response, allowed_hosts=["example.com"])
    assert await restricted.fetch("https://cdn.example.com/a.jpg") == b"jpeg-bytes"
    with pytest.raises(InvalidImageSource, match="not allowed"):
        await fetcher(image_response, allowed_hosts=["flickr.com"]).fetch(
            "https://img.example.com/a.jpg"
        )
    relaxed = fetcher(image_response, allow_http=True, allow_private_networks=True)
    assert await relaxed.fetch("http://internal.example.com/a.jpg") == b"jpeg-bytes"


async def test_follows_redirects_and_checks_every_hop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://cdn.example.com/final"})
        if request.url.path == "/evil":
            return httpx.Response(302, headers={"location": "https://internal.example.com/x"})
        if request.url.path == "/loop":
            return httpx.Response(302, headers={"location": "/loop"})
        return image_response(request)

    client = fetcher(handler)
    assert await client.fetch("https://img.example.com/start") == b"jpeg-bytes"
    with pytest.raises(InvalidImageSource):
        await client.fetch("https://img.example.com/evil")
    with pytest.raises(ImageSourceUnavailable, match="redirected more than"):
        await client.fetch("https://img.example.com/loop")


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(404), ImageSourceUnavailable),
        (
            httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>"),
            UnsupportedImageType,
        ),
        (
            httpx.Response(200, headers={"content-type": "image/png", "content-length": "5000"}),
            ImageTooLarge,
        ),
        (
            httpx.Response(200, headers={"content-type": "image/png"}, content=b"x" * 2048),
            ImageTooLarge,
        ),
    ],
)
async def test_rejects_bad_responses(response: httpx.Response, error: type[Exception]) -> None:
    with pytest.raises(error):
        await fetcher(lambda request: response).fetch("https://img.example.com/a.jpg")


async def test_network_failures_become_unavailable_sources() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    with pytest.raises(ImageSourceUnavailable, match="ConnectTimeout"):
        await fetcher(handler).fetch("https://img.example.com/a.jpg")


def flaky(*responses: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return queue.pop(0) if queue else image_response(request)

    return handler


async def test_retries_rate_limits_honouring_retry_after() -> None:
    sleeps = RecordedSleeps()
    client = fetcher(flaky(httpx.Response(429, headers={"retry-after": "3"})), sleeps)
    assert await client.fetch("https://img.example.com/a.jpg") == b"jpeg-bytes"
    assert sleeps == [3.0]


async def test_backs_off_exponentially_then_gives_up() -> None:
    sleeps = RecordedSleeps()
    client = fetcher(lambda request: httpx.Response(503), sleeps)
    with pytest.raises(ImageSourceUnavailable, match="answered 503"):
        await client.fetch("https://img.example.com/a.jpg")
    assert sleeps == [1.0, 2.0]


async def test_does_not_wait_longer_than_the_retry_limit() -> None:
    sleeps = RecordedSleeps()
    client = fetcher(lambda request: httpx.Response(429, headers={"retry-after": "3600"}), sleeps)
    with pytest.raises(ImageSourceUnavailable, match="answered 429"):
        await client.fetch("https://img.example.com/a.jpg")
    assert sleeps == []


async def test_retries_network_errors_but_not_client_errors() -> None:
    attempts: list[str] = []

    def drop_once(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        if len(attempts) == 1:
            raise httpx.ConnectError("reset", request=request)
        return httpx.Response(404) if request.url.path == "/gone.jpg" else image_response(request)

    sleeps = RecordedSleeps()
    assert await fetcher(drop_once, sleeps).fetch("https://img.example.com/a.jpg") == b"jpeg-bytes"
    with pytest.raises(ImageSourceUnavailable, match="answered 404"):
        await fetcher(drop_once, sleeps).fetch("https://img.example.com/gone.jpg")
    assert attempts == ["/a.jpg", "/a.jpg", "/gone.jpg"]
    assert sleeps == [1.0]
