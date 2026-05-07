"""Add GIST index for service_location geospatial queries

Revision ID: 8e7d6c5b4a2f
Revises: 9f7e6d5c4b3a
Create Date: 2026-04-30 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e7d6c5b4a2f'
down_revision: Union[str, Sequence[str], None] = '9f7e6d5c4b3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add GIST index for service_location geospatial queries."""
    # Create GIST index on service_location field for ST_DWithin/ST_Distance queries
    # GIST (Generalized Search Tree) is optimal for spatial data distance searches
    op.execute(
        'CREATE INDEX "ix_service_listings_service_location" ON service_listings USING gist(service_location)'
    )


def downgrade() -> None:
    """Downgrade schema - remove GIST index."""
    op.drop_index('ix_service_listings_service_location', table_name='service_listings')
