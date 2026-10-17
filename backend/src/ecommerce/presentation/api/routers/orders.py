from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status

from ecommerce.application.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from ecommerce.presentation.api.dependencies import ContainerDep
from ecommerce.presentation.api.schemas.common import PageOut, problem_responses
from ecommerce.presentation.api.schemas.orders import (
    OrderCreate,
    OrderOut,
    OrderSummaryOut,
    QuoteOut,
    QuoteRequest,
)

router = APIRouter(tags=["checkout"])

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Unique key per checkout attempt, retries with the same key are safe",
    ),
]


@router.post(
    "/checkout/quote",
    summary="Price a cart",
    description="Server side subtotal, weight based shipping and total for the given items.",
    responses=problem_responses(404, 409, 422),
)
async def quote_cart(container: ContainerDep, body: QuoteRequest) -> QuoteOut:
    quote = await container.quote_cart.execute([item.to_item() for item in body.items])
    return QuoteOut.from_quote(quote)


@router.post(
    "/orders",
    status_code=status.HTTP_201_CREATED,
    summary="Place an order",
    description=(
        "Reserves stock, charges the simulated payment provider and confirms the order. "
        "A declined payment releases the stock and answers 402 with the failed order id."
    ),
    responses={
        200: {"model": OrderOut, "description": "Replay of an already completed request"},
        **problem_responses(402, 404, 409, 422, 502),
    },
)
async def place_order(
    container: ContainerDep,
    body: OrderCreate,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> OrderOut:
    result = await container.place_order.execute(body.to_command(idempotency_key))
    response.headers["Location"] = f"/api/v1/orders/{result.order.id}"
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return OrderOut.from_domain(result.order)


@router.get("/orders", summary="List orders")
async def list_orders(
    container: ContainerDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    email: Annotated[str | None, Query(max_length=254)] = None,
) -> PageOut[OrderSummaryOut]:
    result = await container.list_orders.execute(PageRequest(page, page_size), email=email)
    return PageOut[OrderSummaryOut].from_page(result, OrderSummaryOut.from_domain)


@router.get("/orders/{order_id}", summary="Get an order", responses=problem_responses(404))
async def get_order(container: ContainerDep, order_id: UUID) -> OrderOut:
    return OrderOut.from_domain(await container.get_order.execute(order_id))
