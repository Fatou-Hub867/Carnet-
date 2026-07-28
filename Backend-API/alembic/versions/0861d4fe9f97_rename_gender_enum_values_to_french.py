"""rename gender enum values to french

Revision ID: 0861d4fe9f97
Revises: 6c332ff88425
Create Date: 2026-07-28 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0861d4fe9f97"
down_revision: Union[str, Sequence[str], None] = "6c332ff88425"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # features/Auth/models.py's Gender enum moved from MALE/FEMALE to
    # HOMME/FEMME. RENAME VALUE keeps every existing row's data intact
    # (unlike drop-and-recreate) and is transaction-safe on Postgres,
    # unlike ADD VALUE.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE gender RENAME VALUE 'MALE' TO 'HOMME'")
        op.execute("ALTER TYPE gender RENAME VALUE 'FEMALE' TO 'FEMME'")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE gender RENAME VALUE 'HOMME' TO 'MALE'")
        op.execute("ALTER TYPE gender RENAME VALUE 'FEMME' TO 'FEMALE'")
