from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RENAMES = (
    ("products", "price_positive"),
    ("products", "stock_non_negative"),
    ("products", "weight_non_negative"),
    ("products", "category_known"),
    ("orders", "status_known"),
    ("orders", "total_consistent"),
    ("order_lines", "quantity_positive"),
)


def _rename(table: str, current: str, target: str) -> None:
    op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {current} TO {target}")


def upgrade() -> None:
    for table, name in RENAMES:
        _rename(table, f"ck_{table}_ck_{table}_{name}", f"ck_{table}_{name}")


def downgrade() -> None:
    for table, name in RENAMES:
        _rename(table, f"ck_{table}_{name}", f"ck_{table}_ck_{table}_{name}")
