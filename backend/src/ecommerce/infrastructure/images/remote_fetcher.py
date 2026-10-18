import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Collection
from urllib.parse import urljoin, urlsplit

import httpx

from ecommerce.application.errors import (
    ImageSourceUnavailable,
    ImageTooLarge,
    InvalidImageSource,
    UnsupportedImageType,
)

MAX_REDIRECTS = 3
DEFAULT_USER_AGENT = "EcommercePlatform/1.0 (product image import)"
_ALLOWED_PORTS = {None, 80, 443}
_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})

type Resolver = Callable[[str], Awaitable[list[str]]]
type Sleeper = Callable[[float], Awaitable[None]]


class _TransientFailure(ImageSourceUnavailable):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


async def resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ImageSourceUnavailable(f"The image host {host} could not be resolved") from exc
    return sorted({str(info[4][0]) for info in infos})


class HttpImageFetcher:
    def __init__(
        self,
        *,
        max_bytes: int,
        timeout_seconds: float = 15.0,
        allowed_hosts: Collection[str] = (),
        allow_http: bool = False,
        allow_private_networks: bool = False,
        user_agent: str = DEFAULT_USER_AGENT,
        max_attempts: int = 3,
        max_retry_wait_seconds: float = 10.0,
        resolver: Resolver = resolve_host,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._max_bytes = max_bytes
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._schemes = {"https", "http"} if allow_http else {"https"}
        self._allow_private = allow_private_networks
        self._user_agent = user_agent
        self._max_attempts = max(1, max_attempts)
        self._max_retry_wait = max_retry_wait_seconds
        self._resolver = resolver
        self._transport = transport
        self._sleep = sleep

    async def fetch(self, url: str) -> bytes:
        headers = {"User-Agent": self._user_agent, "Accept": "image/avif,image/webp,image/*"}
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            headers=headers,
            transport=self._transport,
        ) as client:
            attempt = 1
            while True:
                try:
                    return await self._follow(client, url)
                except _TransientFailure as failure:
                    delay = self._retry_delay(failure, attempt)
                    if attempt >= self._max_attempts or delay is None:
                        raise
                    await self._sleep(delay)
                    attempt += 1

    async def _follow(self, client: httpx.AsyncClient, url: str) -> bytes:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await self._ensure_allowed(current)
            try:
                async with client.stream("GET", current) as response:
                    if response.is_redirect and "location" in response.headers:
                        current = urljoin(current, response.headers["location"])
                        continue
                    return await self._read(response)
            except httpx.TransportError as exc:
                raise _TransientFailure(
                    f"The image could not be downloaded: {type(exc).__name__}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ImageSourceUnavailable(
                    f"The image could not be downloaded: {type(exc).__name__}"
                ) from exc
        raise ImageSourceUnavailable(f"The image URL redirected more than {MAX_REDIRECTS} times")

    def _retry_delay(self, failure: _TransientFailure, attempt: int) -> float | None:
        if failure.retry_after is None:
            return min(float(2 ** (attempt - 1)), self._max_retry_wait)
        if failure.retry_after > self._max_retry_wait:
            return None
        return failure.retry_after

    async def _ensure_allowed(self, url: str) -> None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in self._schemes:
            allowed = " or ".join(sorted(self._schemes))
            raise InvalidImageSource(f"The image URL must use {allowed}")
        if not host or parts.username or parts.password:
            raise InvalidImageSource("The image URL must have a host and no credentials")
        if parts.port not in _ALLOWED_PORTS and not self._allow_private:
            raise InvalidImageSource("The image URL must use the default port")
        if self._allowed_hosts and not any(
            host == allowed or host.endswith(f".{allowed}") for allowed in self._allowed_hosts
        ):
            raise InvalidImageSource(f"Images from {host} are not allowed")
        if self._allow_private:
            return
        for address in await self._resolver(host):
            ip = ipaddress.ip_address(address)
            if not ip.is_global or ip.is_multicast:
                raise InvalidImageSource("The image URL points to a private or reserved address")

    async def _read(self, response: httpx.Response) -> bytes:
        if response.status_code in _RETRYABLE_STATUSES:
            raise _TransientFailure(
                f"The image URL answered {response.status_code}",
                retry_after=_seconds(response.headers.get("retry-after")),
            )
        if response.status_code != httpx.codes.OK:
            raise ImageSourceUnavailable(f"The image URL answered {response.status_code}")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise UnsupportedImageType("The URL does not point to an image")
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self._max_bytes:
            raise ImageTooLarge(f"The image must not exceed {self._max_bytes} bytes")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise ImageTooLarge(f"The image must not exceed {self._max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)


def _seconds(value: str | None) -> float | None:
    if value is None or not value.strip().isdigit():
        return None
    return float(value.strip())
