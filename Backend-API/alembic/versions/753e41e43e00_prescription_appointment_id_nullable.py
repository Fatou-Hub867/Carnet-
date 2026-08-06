"""prescription appointment_id nullable

Revision ID: 753e41e43e00
Revises: 23f99d079a14
Create Date: 2026-08-05 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "753e41e43e00"
down_revision: Union[str, Sequence[str], None] = "23f99d079a14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "prescriptions",
        "appointment_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "prescriptions",
        "appointment_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
