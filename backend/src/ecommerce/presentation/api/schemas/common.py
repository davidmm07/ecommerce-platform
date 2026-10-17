from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from ecommerce.application.pagination import Page


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldErrorOut(ApiModel):
    field: str = Field(examples=["price"])
    message: str = Field(examples=["must be greater than 0"])


class ProblemOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(examples=["urn:ecommerce:problem:validation_failed"])
    title: str = Field(examples=["Validation failed"])
    status: int = Field(examples=[422])
    detail: str = Field(examples=["price: must be greater than 0"])
    instance: str = Field(examples=["/api/v1/products"])
    code: str = Field(examples=["validation_failed"])
    request_id: str | None = Field(default=None, examples=["5f0c6b1e2d7a4c41a0f3"])
    errors: list[FieldErrorOut] | None = None


class PageOut[T](ApiModel):
    items: list[T]
    page: int = Field(examples=[1])
    page_size: int = Field(examples=[20])
    total: int = Field(examples=[42])
    total_pages: int = Field(examples=[3])

    @classmethod
    def from_page[S](cls, page: Page[S], convert: Callable[[S], T]) -> "PageOut[T]":
        return cls(
            items=[convert(item) for item in page.items],
            page=page.request.number,
            page_size=page.request.size,
            total=page.total,
            total_pages=page.total_pages,
        )


def problem_responses(*statuses: int) -> dict[int | str, dict[str, object]]:
    return {
        status: {"model": ProblemOut, "content": {"application/problem+json": {}}}
        for status in statuses
    }
