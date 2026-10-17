import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from uuid import UUID

from ecommerce.application.errors import (
    ApplicationError,
    IdempotencyKeyReused,
    NotFoundError,
    PaymentDeclined,
    PaymentUnavailable,
    RequestInProgress,
)
from ecommerce.application.ordering.cart import normalize_items, price_lines
from ecommerce.application.ordering.commands import CartItem, PlaceOrderCommand
from ecommerce.application.ports.payments import (
    ChargeRequest,
    ChargeResult,
    PaymentGateway,
    PaymentGatewayError,
)
from ecommerce.application.ports.system import Clock, IdFactory
from ecommerce.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from ecommerce.domain.errors import FieldErrors, InvalidValue
from ecommerce.domain.ordering.order import (
    Customer,
    Order,
    OrderStatus,
    PaymentSummary,
    ShippingAddress,
)
from ecommerce.domain.ordering.pricing import ShippingPolicy
from ecommerce.domain.payments.card import PaymentCard

PROCESSING_ERROR = "processing_error"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{8,100}$")

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlaceOrderResult:
    order: Order
    replayed: bool


@dataclass(frozen=True, slots=True)
class _Checkout:
    items: tuple[CartItem, ...]
    customer: Customer
    shipping_address: ShippingAddress
    card: PaymentCard
    fingerprint: str


class PlaceOrder:
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        payment_gateway: PaymentGateway,
        shipping_policy: ShippingPolicy,
        clock: Clock,
        new_id: IdFactory,
    ) -> None:
        self._uow_factory = uow_factory
        self._payment_gateway = payment_gateway
        self._shipping_policy = shipping_policy
        self._clock = clock
        self._new_id = new_id

    async def execute(self, command: PlaceOrderCommand) -> PlaceOrderResult:
        checkout = _validate(command)
        async with self._uow_factory() as uow:
            existing = await uow.orders.get_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return _replay(existing, checkout.fingerprint)
            order = await self._reserve_stock(uow, command.idempotency_key, checkout)
            await uow.commit()
        charge = await self._charge(order, checkout.card, command.idempotency_key)
        order = await self._settle(order.id, charge, checkout.card)
        if order.status is OrderStatus.PAYMENT_FAILED:
            raise _failure_of(order)
        return PlaceOrderResult(order=order, replayed=False)

    async def _reserve_stock(
        self, uow: UnitOfWork, idempotency_key: str, checkout: _Checkout
    ) -> Order:
        now = self._clock.now()
        products = await uow.products.get_many(
            [item.product_id for item in checkout.items], lock=True
        )
        lines = price_lines(checkout.items, products)
        by_id = {product.id: product for product in products}
        for item in checkout.items:
            product = by_id[item.product_id]
            product.reserve(item.quantity, now)
            await uow.products.update(product)
        order = Order.place(
            order_id=self._new_id(),
            customer=checkout.customer,
            shipping_address=checkout.shipping_address,
            lines=lines,
            shipping_policy=self._shipping_policy,
            idempotency_key=idempotency_key,
            request_fingerprint=checkout.fingerprint,
            now=now,
        )
        await uow.orders.add(order)
        return order

    async def _charge(
        self, order: Order, card: PaymentCard, idempotency_key: str
    ) -> ChargeResult | None:
        request = ChargeRequest(
            amount=order.totals.total,
            card=card,
            reference=order.number,
            idempotency_key=idempotency_key,
        )
        try:
            return await self._payment_gateway.charge(request)
        except PaymentGatewayError:
            logger.warning("payment provider failed", extra={"order_number": order.number})
            return None

    async def _settle(
        self, order_id: UUID, charge: ChargeResult | None, card: PaymentCard
    ) -> Order:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id, lock=True)
            if order is None:
                raise NotFoundError("Order", order_id)
            if charge is not None and charge.approved:
                summary = PaymentSummary(
                    card_brand=charge.card_brand,
                    card_last4=charge.card_last4,
                    reference=charge.reference,
                )
                order.mark_paid(summary, now)
            else:
                summary = PaymentSummary(
                    card_brand=card.brand.value,
                    card_last4=card.last4,
                    reference=charge.reference if charge else None,
                    failure_code=(charge.decline_code if charge else None) or PROCESSING_ERROR,
                )
                order.mark_payment_failed(summary, now)
                await _release_stock(uow, order)
            await uow.orders.update(order)
            await uow.commit()
        return order


async def _release_stock(uow: UnitOfWork, order: Order) -> None:
    products = await uow.products.get_many(
        [line.product_id for line in order.lines], lock=True, include_archived=True
    )
    by_id = {product.id: product for product in products}
    for line in order.lines:
        product = by_id.get(line.product_id)
        if product is not None:
            product.release(line.quantity, order.updated_at)
            await uow.products.update(product)


def _validate(command: PlaceOrderCommand) -> _Checkout:
    errors = FieldErrors()
    with errors.collect("idempotency_key"):
        if not _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key):
            raise InvalidValue("must be 8 to 100 letters, digits, hyphens or underscores")
    with errors.collect():
        items = normalize_items(command.items)
    with errors.collect("customer"):
        customer = Customer.build(name=command.customer.name, email=command.customer.email)
    with errors.collect("shipping_address"):
        address = command.shipping_address
        shipping_address = ShippingAddress.build(
            line1=address.line1,
            city=address.city,
            postal_code=address.postal_code,
            country=address.country,
        )
    with errors.collect("payment"):
        card_input = command.card
        card = PaymentCard.parse(
            number=card_input.number,
            expiry_month=card_input.expiry_month,
            expiry_year=card_input.expiry_year,
            cvc=card_input.cvc,
            holder_name=card_input.holder_name,
        )
    errors.raise_if_any()
    return _Checkout(
        items=items,
        customer=customer,
        shipping_address=shipping_address,
        card=card,
        fingerprint=_fingerprint(items, customer, shipping_address, card),
    )


def _fingerprint(
    items: tuple[CartItem, ...],
    customer: Customer,
    shipping_address: ShippingAddress,
    card: PaymentCard,
) -> str:
    payload = {
        "items": sorted([str(item.product_id), item.quantity] for item in items),
        "customer": asdict(customer),
        "shipping_address": asdict(shipping_address),
        "card": [card.last4, card.expiry_month, card.expiry_year, card.holder_name],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _replay(order: Order, fingerprint: str) -> PlaceOrderResult:
    if order.request_fingerprint != fingerprint:
        raise IdempotencyKeyReused()
    if order.status is OrderStatus.PENDING_PAYMENT:
        raise RequestInProgress()
    if order.status is OrderStatus.PAYMENT_FAILED:
        raise _failure_of(order)
    return PlaceOrderResult(order=order, replayed=True)


def _failure_of(order: Order) -> ApplicationError:
    code = order.payment.failure_code if order.payment else None
    if code is None or code == PROCESSING_ERROR:
        return PaymentUnavailable(order.id, order.number)
    return PaymentDeclined(order.id, order.number, code)
