"""add RBAC and approval fields to db_connections

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-04-15 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add RBAC columns to db_connections
    op.add_column('db_connections',
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True))
    op.add_column('db_connections',
        sa.Column('status', sa.String(), nullable=False,
                  server_default='approved'))
    op.add_column('db_connections',
        sa.Column('is_admin_owned', sa.Boolean(), nullable=False,
                  server_default='true'))

    op.create_index('ix_db_connections_created_by', 'db_connections', ['created_by'])
    op.create_index('ix_db_connections_status',     'db_connections', ['status'])


def downgrade() -> None:
    op.drop_index('ix_db_connections_status',     table_name='db_connections')
    op.drop_index('ix_db_connections_created_by', table_name='db_connections')
    op.drop_column('db_connections', 'is_admin_owned')
    op.drop_column('db_connections', 'status')
    op.drop_column('db_connections', 'created_by')
