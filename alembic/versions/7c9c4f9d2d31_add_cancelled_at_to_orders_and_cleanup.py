"""add_cancelled_at_to_orders_and_cleanup

Revision ID: 7c9c4f9d2d31
Revises: 4340c8e4afc8
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c9c4f9d2d31'
down_revision: Union[str, Sequence[str], None] = '4340c8e4afc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('cancelledAt', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_orders_status_cancelled_at', 'orders', ['status', 'cancelledAt'], unique=False)

    op.execute(
        sa.text(
            'UPDATE orders '
            'SET "cancelledAt" = updated_at '
            'WHERE status = :status AND "cancelledAt" IS NULL'
        ).bindparams(status='cancelled')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_orders_status_cancelled_at', table_name='orders')
    op.drop_column('orders', 'cancelledAt')