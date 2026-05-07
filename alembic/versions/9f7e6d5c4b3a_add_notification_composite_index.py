"""Add composite index for notification queries

Revision ID: 9f7e6d5c4b3a
Revises: aa880906f51a
Create Date: 2026-04-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f7e6d5c4b3a'
down_revision: Union[str, Sequence[str], None] = 'aa880906f51a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add composite index for notification queries."""
    # Create composite index on (userId, isRead, created_at DESC)
    # This optimizes the mark_all_as_read query: WHERE userId=? AND isRead=False
    op.create_index(
        'ix_notifications_userid_isread_createdat',
        'notifications',
        ['userId', 'isRead', sa.text('created_at DESC')],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - remove composite index."""
    op.drop_index('ix_notifications_userid_isread_createdat', table_name='notifications')
