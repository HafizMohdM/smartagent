"""
Refactor Query Model: Add generated_sql and remove result_json.

Revision ID: 2026_04_17_query_refactor
Revises: f3e123abc456
Create Date: 2026-04-17 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_04_17_query_refactor'
down_revision = '2054decf4bf5'
branch_labels = None

depends_on = None

def upgrade():
    # 1. Add generated_sql to queries
    op.add_column('queries', sa.Column('generated_sql', sa.Text(), nullable=True))
    
    # 2. Add comment for role clarification
    op.execute("COMMENT ON COLUMN query_executions.result_json IS 'LEGACY: Scheduled for deletion after backfill.'")

    # NOTE: We do NOT drop result_json here yet because we need to run the backfill script first.
    # In a production pipeline, this would be a multi-phase migration.
    # For this task, we'll provide the 'Cleanup' migration separately once backfill is confirmed.

def downgrade():
    op.drop_column('queries', 'generated_sql')
