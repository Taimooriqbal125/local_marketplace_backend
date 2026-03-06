"""add_cloudinary_public_id_to_listing_media

Revision ID: 4d5f96ffb82f
Revises: c4e1e3dbbfdf
Create Date: 2026-03-06 01:38:29.369910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d5f96ffb82f'
down_revision: Union[str, Sequence[str], None] = 'c4e1e3dbbfdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('listing_media', sa.Column('cloudinaryPublicId', sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('listing_media', 'cloudinaryPublicId')
