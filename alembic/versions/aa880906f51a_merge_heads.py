"""Merge heads

Revision ID: aa880906f51a
Revises: 3af94274cd19, 7c9c4f9d2d31
Create Date: 2026-04-30 17:04:02.736982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa880906f51a'
down_revision: Union[str, Sequence[str], None] = ('3af94274cd19', '7c9c4f9d2d31')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
