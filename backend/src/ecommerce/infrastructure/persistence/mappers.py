from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.product import Product
from ecommerce.domain.catalog.sku import Sku
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.order import (
    Customer,
    Order,
    OrderLine,
    OrderStatus,
    PaymentSummary,
    ShippingAddress,
)
from ecommerce.domain.ordering.pricing import OrderTotals
from ecommerce.infrastructure.persistence.models import OrderLineRecord, OrderRecord, ProductRecord


class ProductMapper:
    @staticmethod
    def to_record(product: Product) -> ProductRecord:
        record = ProductRecord(id=product.id, created_at=product.created_at)
        ProductMapper.apply(product, record)
        return record

    @staticmethod
    def apply(product: Product, record: ProductRecord) -> None:
        record.sku = product.sku.value
        record.name = product.name
        record.description = product.description
        record.category = product.category.value
        record.price = product.price.amount
        record.currency = product.price.currency
        record.stock = product.stock
        record.weight_kg = product.weight_kg
        record.updated_at = product.updated_at
        record.archived_at = product.archived_at

    @staticmethod
    def to_domain(record: ProductRecord) -> Product:
        return Product(
            id=record.id,
            sku=Sku(record.sku),
            name=record.name,
            description=record.description,
            category=Category(record.category),
            price=Money(record.price, record.currency),
            stock=record.stock,
            weight_kg=record.weight_kg,
            created_at=record.created_at,
            updated_at=record.updated_at,
            version=record.version,
            archived_at=record.archived_at,
        )


class OrderMapper:
    @staticmethod
    def to_record(order: Order) -> OrderRecord:
        record = OrderRecord(
            id=order.id,
            number=order.number,
            customer_name=order.customer.name,
            customer_email=order.customer.email,
            shipping_line1=order.shipping_address.line1,
            shipping_city=order.shipping_address.city,
            shipping_postal_code=order.shipping_address.postal_code,
            shipping_country=order.shipping_address.country,
            currency=order.totals.total.currency,
            subtotal=order.totals.subtotal.amount,
            shipping_cost=order.totals.shipping.amount,
            total=order.totals.total.amount,
            total_weight_kg=order.totals.total_weight_kg,
            idempotency_key=order.idempotency_key,
            request_fingerprint=order.request_fingerprint,
            created_at=order.created_at,
            lines=[
                OrderLineRecord(
                    position=position,
                    product_id=line.product_id,
                    sku=line.sku,
                    name=line.name,
                    unit_price=line.unit_price.amount,
                    quantity=line.quantity,
                    unit_weight_kg=line.unit_weight_kg,
                    line_total=line.line_total.amount,
                )
                for position, line in enumerate(order.lines, start=1)
            ],
        )
        OrderMapper.apply(order, record)
        return record

    @staticmethod
    def apply(order: Order, record: OrderRecord) -> None:
        payment = order.payment
        record.status = order.status.value
        record.payment_reference = payment.reference if payment else None
        record.card_brand = payment.card_brand if payment else None
        record.card_last4 = payment.card_last4 if payment else None
        record.payment_failure_code = payment.failure_code if payment else None
        record.updated_at = order.updated_at

    @staticmethod
    def to_domain(record: OrderRecord) -> Order:
        currency = record.currency
        payment = (
            PaymentSummary(
                card_brand=record.card_brand,
                card_last4=record.card_last4 or "",
                reference=record.payment_reference,
                failure_code=record.payment_failure_code,
            )
            if record.card_brand is not None
            else None
        )
        return Order(
            id=record.id,
            number=record.number,
            status=OrderStatus(record.status),
            customer=Customer(name=record.customer_name, email=record.customer_email),
            shipping_address=ShippingAddress(
                line1=record.shipping_line1,
                city=record.shipping_city,
                postal_code=record.shipping_postal_code,
                country=record.shipping_country,
            ),
            lines=tuple(
                OrderLine(
                    product_id=line.product_id,
                    sku=line.sku,
                    name=line.name,
                    unit_price=Money(line.unit_price, currency),
                    quantity=line.quantity,
                    unit_weight_kg=line.unit_weight_kg,
                )
                for line in record.lines
            ),
            totals=OrderTotals(
                subtotal=Money(record.subtotal, currency),
                shipping=Money(record.shipping_cost, currency),
                total=Money(record.total, currency),
                total_weight_kg=record.total_weight_kg,
            ),
            idempotency_key=record.idempotency_key,
            request_fingerprint=record.request_fingerprint,
            created_at=record.created_at,
            updated_at=record.updated_at,
            payment=payment,
            version=record.version,
        )
