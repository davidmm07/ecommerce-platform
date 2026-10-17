from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, SecretStr

from ecommerce.application.ordering.cart import CartQuote
from ecommerce.application.ordering.commands import (
    AddressInput,
    CardInput,
    CartItem,
    CustomerInput,
    PlaceOrderCommand,
)
from ecommerce.domain.ordering.order import (
    MAX_LINES_PER_ORDER,
    MAX_QUANTITY_PER_LINE,
    Order,
    OrderLine,
    OrderStatus,
)
from ecommerce.domain.ordering.pricing import OrderTotals
from ecommerce.presentation.api.schemas.common import ApiModel


class CartItemIn(ApiModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_LINE, examples=[2])

    def to_item(self) -> CartItem:
        return CartItem(product_id=self.product_id, quantity=self.quantity)


class QuoteRequest(ApiModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=MAX_LINES_PER_ORDER)


class CustomerIn(ApiModel):
    name: str = Field(min_length=1, max_length=120, examples=["Ada Lovelace"])
    email: str = Field(min_length=3, max_length=254, examples=["ada@example.com"])


class AddressIn(ApiModel):
    line1: str = Field(min_length=1, max_length=200, examples=["221B Baker Street"])
    city: str = Field(min_length=1, max_length=100, examples=["London"])
    postal_code: str = Field(min_length=2, max_length=15, examples=["NW1 6XE"])
    country: str = Field(min_length=2, max_length=2, examples=["GB"])


class PaymentIn(ApiModel):
    card_number: SecretStr = Field(min_length=12, max_length=23, examples=["4242 4242 4242 4242"])
    expiry_month: int = Field(ge=1, le=12, examples=[12])
    expiry_year: int = Field(ge=2000, le=2100, examples=[2030])
    cvc: SecretStr = Field(min_length=3, max_length=4, examples=["123"])
    holder_name: str = Field(min_length=1, max_length=100, examples=["Ada Lovelace"])


class OrderCreate(ApiModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=MAX_LINES_PER_ORDER)
    customer: CustomerIn
    shipping_address: AddressIn
    payment: PaymentIn

    def to_command(self, idempotency_key: str) -> PlaceOrderCommand:
        return PlaceOrderCommand(
            idempotency_key=idempotency_key,
            items=tuple(item.to_item() for item in self.items),
            customer=CustomerInput(name=self.customer.name, email=self.customer.email),
            shipping_address=AddressInput(
                line1=self.shipping_address.line1,
                city=self.shipping_address.city,
                postal_code=self.shipping_address.postal_code,
                country=self.shipping_address.country,
            ),
            card=CardInput(
                number=self.payment.card_number.get_secret_value(),
                expiry_month=self.payment.expiry_month,
                expiry_year=self.payment.expiry_year,
                cvc=self.payment.cvc.get_secret_value(),
                holder_name=self.payment.holder_name,
            ),
        )


class OrderLineOut(ApiModel):
    product_id: UUID
    sku: str
    name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    unit_weight_kg: Decimal

    @classmethod
    def from_domain(cls, line: OrderLine) -> "OrderLineOut":
        return cls(
            product_id=line.product_id,
            sku=line.sku,
            name=line.name,
            unit_price=line.unit_price.amount,
            quantity=line.quantity,
            line_total=line.line_total.amount,
            unit_weight_kg=line.unit_weight_kg,
        )


class TotalsOut(ApiModel):
    subtotal: Decimal
    shipping: Decimal
    total: Decimal
    total_weight_kg: Decimal
    currency: str

    @classmethod
    def from_domain(cls, totals: OrderTotals) -> "TotalsOut":
        return cls(
            subtotal=totals.subtotal.amount,
            shipping=totals.shipping.amount,
            total=totals.total.amount,
            total_weight_kg=totals.total_weight_kg,
            currency=totals.total.currency,
        )


class QuoteOut(ApiModel):
    lines: list[OrderLineOut]
    totals: TotalsOut

    @classmethod
    def from_quote(cls, quote: CartQuote) -> "QuoteOut":
        return cls(
            lines=[OrderLineOut.from_domain(line) for line in quote.lines],
            totals=TotalsOut.from_domain(quote.totals),
        )


class CustomerOut(ApiModel):
    name: str
    email: str


class AddressOut(ApiModel):
    line1: str
    city: str
    postal_code: str
    country: str


class PaymentOut(ApiModel):
    card_brand: str
    card_last4: str
    reference: str | None
    failure_code: str | None


class OrderOut(ApiModel):
    id: UUID
    number: str
    status: OrderStatus
    customer: CustomerOut
    shipping_address: AddressOut
    lines: list[OrderLineOut]
    totals: TotalsOut
    payment: PaymentOut | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, order: Order) -> "OrderOut":
        address = order.shipping_address
        payment = order.payment
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            customer=CustomerOut(name=order.customer.name, email=order.customer.email),
            shipping_address=AddressOut(
                line1=address.line1,
                city=address.city,
                postal_code=address.postal_code,
                country=address.country,
            ),
            lines=[OrderLineOut.from_domain(line) for line in order.lines],
            totals=TotalsOut.from_domain(order.totals),
            payment=(
                PaymentOut(
                    card_brand=payment.card_brand,
                    card_last4=payment.card_last4,
                    reference=payment.reference,
                    failure_code=payment.failure_code,
                )
                if payment
                else None
            ),
            created_at=order.created_at,
            updated_at=order.updated_at,
        )


class OrderSummaryOut(ApiModel):
    id: UUID
    number: str
    status: OrderStatus
    customer_name: str
    customer_email: str
    item_count: int
    total: Decimal
    currency: str
    created_at: datetime

    @classmethod
    def from_domain(cls, order: Order) -> "OrderSummaryOut":
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            customer_name=order.customer.name,
            customer_email=order.customer.email,
            item_count=order.item_count,
            total=order.totals.total.amount,
            currency=order.totals.total.currency,
            created_at=order.created_at,
        )
