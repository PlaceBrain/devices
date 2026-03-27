"""drop mqtt_credentials table

Revision ID: 8b4ab59d4c4a
Revises: a47ef0cd1520
Create Date: 2026-03-27 12:54:08.016310

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b4ab59d4c4a"
down_revision: str | Sequence[str] | None = "a47ef0cd1520"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_mqtt_credentials_user_id", table_name="mqtt_credentials")
    op.drop_table("mqtt_credentials")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "mqtt_credentials",
        op.Column("user_id", op.UUID(), nullable=False),
        op.Column("username", op.String(length=255), nullable=False, unique=True),
        op.Column("password_hash", op.String(length=255), nullable=False),
        op.Column("allowed_place_ids", op.JSON(), nullable=False),
        op.Column("expires_at", op.DateTime(timezone=True), nullable=False),
        op.Column("id", op.UUID(), nullable=False),
        op.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mqtt_credentials_user_id", "mqtt_credentials", ["user_id"])
