"""set_profile_sellerstatus_default_active

Revision ID: a1f3c9e7b2d4
Revises: 6a5af82dc207
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f3c9e7b2d4"
down_revision: Union[str, Sequence[str], None] = "6a5af82dc207"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "profiles",
        "sellerStatus",
        existing_type=sa.String(length=20),
        server_default=sa.text("'active'"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "profiles",
        "sellerStatus",
        existing_type=sa.String(length=20),
        server_default=sa.text("'none'"),
        existing_nullable=False,
    )
