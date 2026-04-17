"""
Cleanup Query Model: Drop result_json from executions.

Revision ID: 2026_04_17_query_cleanup
Revises: 2026_04_17_query_refactor
Create Date: 2026-04-17 10:35:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_04_17_query_cleanup'
down_revision = '2026_04_17_query_refactor'
branch_labels = None
depends_on = None

def upgrade():
    # Guarantee 3 & 4: Hard Deletion of result_json
    # We drop the column entirely to ensure no code can rely on stored snapshots.
    op.drop_column('query_executions', 'result_json')

def downgrade():
    # If we downgrade, we recreate the column but data is lost (as documented).
    op.add_column('query_executions', sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
