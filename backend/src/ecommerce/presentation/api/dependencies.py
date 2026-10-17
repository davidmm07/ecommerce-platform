from typing import Annotated, cast

from fastapi import Depends, Header, HTTPException, Request

from ecommerce.container import Container
from ecommerce.presentation.api.media import MediaUrls


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def get_media_urls(request: Request) -> MediaUrls:
    return cast(MediaUrls, request.app.state.media_urls)


def expected_version(
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description='Optimistic concurrency token returned in the ETag header, e.g. "3"',
        ),
    ] = None,
) -> int | None:
    if if_match is None or if_match.strip() == "*":
        return None
    token = if_match.strip().removeprefix("W/").strip('"')
    if not (token.isascii() and token.isdigit()):
        raise HTTPException(status_code=400, detail='If-Match must be an ETag such as "3"')
    return int(token)


def etag_for(version: int) -> str:
    return f'"{version}"'


ContainerDep = Annotated[Container, Depends(get_container)]
ExpectedVersionDep = Annotated[int | None, Depends(expected_version)]
MediaUrlsDep = Annotated[MediaUrls, Depends(get_media_urls)]
