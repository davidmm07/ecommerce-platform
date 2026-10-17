from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        op.f("ck_products_image_is_object"),
        "products",
        "image IS NULL OR jsonb_typeof(image) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_products_image_is_object"), "products", type_="check")
    op.drop_column("products", "image")
