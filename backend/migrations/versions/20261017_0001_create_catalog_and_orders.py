from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
    "accessories",
    "beauty",
    "books",
    "clothing",
    "electronics",
    "food-beverage",
    "footwear",
    "games",
    "gifts",
    "health",
    "home-office",
    "kitchen",
    "misc",
    "outdoors",
    "pets",
    "sports",
    "stationery",
    "tools",
)
ORDER_STATUSES = ("pending_payment", "paid", "payment_failed")
SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english'::regconfig, coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(sku, '')), 'A') || "
    "setweight(to_tsvector('english'::regconfig, coalesce(description, '')), 'B')"
)


def _in_list(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_SQL, persisted=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.CheckConstraint("price > 0", name="ck_products_price_positive"),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
        sa.CheckConstraint("weight_kg >= 0", name="ck_products_weight_non_negative"),
        sa.CheckConstraint(_in_list("category", CATEGORIES), name="ck_products_category_known"),
    )
    op.create_index(
        "uq_products_sku_active",
        "products",
        ["sku"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_products_search_vector", "products", ["search_vector"], postgresql_using="gin"
    )
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_price", "products", ["price"])
    op.create_index("ix_products_created_at", "products", ["created_at"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("shipping_line1", sa.String(200), nullable=False),
        sa.Column("shipping_city", sa.String(100), nullable=False),
        sa.Column("shipping_postal_code", sa.String(15), nullable=False),
        sa.Column("shipping_country", sa.String(2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_weight_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("payment_reference", sa.String(64), nullable=True),
        sa.Column("card_brand", sa.String(20), nullable=True),
        sa.Column("card_last4", sa.String(4), nullable=True),
        sa.Column("payment_failure_code", sa.String(40), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        sa.UniqueConstraint("number", name="uq_orders_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        sa.CheckConstraint(_in_list("status", ORDER_STATUSES), name="ck_orders_status_known"),
        sa.CheckConstraint("total = subtotal + shipping_cost", name="ck_orders_total_consistent"),
    )
    op.create_index("ix_orders_customer_email", "orders", ["customer_email"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])

    op.create_table(
        "order_lines",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("order_id", "position", name="pk_order_lines"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_lines_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_order_lines_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_order_lines_quantity_positive"),
    )
    op.create_index("ix_order_lines_product_id", "order_lines", ["product_id"])


def downgrade() -> None:
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("products")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
