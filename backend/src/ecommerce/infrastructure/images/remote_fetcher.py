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

type Resolver = Callable[[str], Awaitable[list[str]]]


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
        resolver: Resolver = resolve_host,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._schemes = {"https", "http"} if allow_http else {"https"}
        self._allow_private = allow_private_networks
        self._user_agent = user_agent
        self._resolver = resolver
        self._transport = transport

    async def fetch(self, url: str) -> bytes:
        headers = {"User-Agent": self._user_agent, "Accept": "image/avif,image/webp,image/*"}
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
            headers=headers,
            transport=self._transport,
        ) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                await self._ensure_allowed(current)
                try:
                    async with client.stream("GET", current) as response:
                        if response.is_redirect and "location" in response.headers:
                            current = urljoin(current, response.headers["location"])
                            continue
                        return await self._read(response)
                except httpx.HTTPError as exc:
                    raise ImageSourceUnavailable(
                        f"The image could not be downloaded: {type(exc).__name__}"
                    ) from exc
        raise ImageSourceUnavailable(f"The image URL redirected more than {MAX_REDIRECTS} times")

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
