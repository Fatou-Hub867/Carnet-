"""add weight_kg and photo_file_key fields

Revision ID: a1b2c3d4e5f6
Revises: f2a66aa2414c
Create Date: 2026-08-02 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2a66aa2414c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("patients", sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "patients", sa.Column("photo_file_key", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "doctors", sa.Column("photo_file_key", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("doctors", "photo_file_key")
    op.drop_column("patients", "photo_file_key")
    op.drop_column("patients", "weight_kg")
