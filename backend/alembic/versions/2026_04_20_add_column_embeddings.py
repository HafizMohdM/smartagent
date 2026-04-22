"""
Add column_embeddings to table_metadata_store.

Revision ID: 2026_04_20_col_embeddings
Revises: 2026_04_17_query_cleanup
Create Date: 2026-04-20 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_04_20_col_embeddings'
down_revision = '2026_04_17_query_cleanup'
branch_labels = None
depends_on = None

def upgrade():
    # Add column_embeddings JSONB field for per-column embedding cache
    op.add_column('table_metadata_store', sa.Column('column_embeddings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

def downgrade():
    # Remove column_embeddings field
    op.drop_column('table_metadata_store', 'column_embeddings')
