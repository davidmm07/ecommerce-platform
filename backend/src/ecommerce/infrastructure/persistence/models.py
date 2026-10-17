from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ecommerce.domain.catalog.category import Category
from ecommerce.domain.ordering.order import OrderStatus

SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english'::regconfig, coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(sku, '')), 'A') || "
    "setweight(to_tsvector('english'::regconfig, coalesce(description, '')), 'B')"
)


def _in_list(column: str, values: list[str]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000))
    category: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    stock: Mapped[int]
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    version: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed(SEARCH_VECTOR_SQL, persisted=True), deferred=True
    )

    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("weight_kg >= 0", name="weight_non_negative"),
        CheckConstraint(_in_list("category", [c.value for c in Category]), name="category_known"),
        CheckConstraint("image IS NULL OR jsonb_typeof(image) = 'object'", name="image_is_object"),
        Index(
            "uq_products_sku_active",
            "sku",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_products_category", "category"),
        Index("ix_products_price", "price"),
        Index("ix_products_created_at", "created_at"),
    )


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(16), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254))
    shipping_line1: Mapped[str] = mapped_column(String(200))
    shipping_city: Mapped[str] = mapped_column(String(100))
    shipping_postal_code: Mapped[str] = mapped_column(String(15))
    shipping_country: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    payment_reference: Mapped[str | None] = mapped_column(String(64))
    card_brand: Mapped[str | None] = mapped_column(String(20))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    payment_failure_code: Mapped[str | None] = mapped_column(String(40))
    version: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list[OrderLineRecord]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderLineRecord.position",
        lazy="raise",
    )

    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        CheckConstraint(_in_list("status", [s.value for s in OrderStatus]), name="status_known"),
        CheckConstraint("total = subtotal + shipping_cost", name="total_consistent"),
        Index("ix_orders_customer_email", "customer_email"),
        Index("ix_orders_created_at", "created_at"),
    )


class OrderLineRecord(Base):
    __tablename__ = "order_lines"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    sku: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int]
    unit_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[OrderRecord] = relationship(back_populates="lines", lazy="raise")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_order_lines_product_id", "product_id"),
    )
