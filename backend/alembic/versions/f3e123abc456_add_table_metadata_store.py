"""add_table_metadata_store

Revision ID: f3e123abc456
Revises: a4b16ff0c230
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'f3e123abc456'
down_revision: Union[str, Sequence[str], None] = 'a4b16ff0c230'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('table_metadata_store',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('schema_name', sa.String(), nullable=False, server_default='public'),
        sa.Column('table_name', sa.String(), nullable=False),
        sa.Column('columns', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('synonyms', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('relationships', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['db_connections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connection_id', 'schema_name', 'table_name', name='uq_connection_schema_table')
    )
    op.create_index(op.f('ix_table_metadata_store_connection_id'), 'table_metadata_store', ['connection_id'], unique=False)
    
    # Ensure pgvector extension is present (it should be from previous migrations, but safe check)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # HNSW Index for cosine similarity
    try:
        op.execute("CREATE INDEX idx_table_metadata_embedding ON table_metadata_store USING hnsw (embedding vector_cosine_ops)")
    except Exception as e:
        print(f"Warning: Could not create HNSW index, falling back to IVFFlat: {e}")
        op.execute("CREATE INDEX idx_table_metadata_embedding_ivf ON table_metadata_store USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_table_metadata_store_connection_id'), table_name='table_metadata_store')
    op.execute("DROP INDEX IF EXISTS idx_table_metadata_embedding")
    op.execute("DROP INDEX IF EXISTS idx_table_metadata_embedding_ivf")
    op.drop_table('table_metadata_store')
