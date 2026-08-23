"""Add service_embeddings table for AI search

Revision ID: e5f6a7b8c9d0
Revises: d864e7f8ba7a
Create Date: 2026-08-19 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd864e7f8ba7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create service_embeddings table
    op.create_table('service_embeddings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['service_listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('listing_id', name='uq_service_embeddings_listing_id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_service_embeddings_id'), 'service_embeddings', ['id'], unique=False)
    op.create_index(op.f('ix_service_embeddings_listing_id'), 'service_embeddings', ['listing_id'], unique=False)
    
    # Create IVFFlat index for fast similarity search
    # Note: IVFFlat requires data to be present before creating index
    # For initial setup, we'll use a simpler approach
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_service_embeddings_cosine 
        ON service_embeddings 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_service_embeddings_listing_id'), table_name='service_embeddings')
    op.drop_index(op.f('ix_service_embeddings_id'), table_name='service_embeddings')
    op.execute("DROP INDEX IF EXISTS ix_service_embeddings_cosine")
    op.drop_table('service_embeddings')
