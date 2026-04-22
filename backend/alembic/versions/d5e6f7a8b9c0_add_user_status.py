"""add status column to users

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-15 15:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column — existing users (admins) default to approved
    op.add_column('users',
        sa.Column('status', sa.String(), nullable=False, server_default='approved'))
    # Set is_active default to False for new registrations
    # (existing rows keep their current is_active value)
    op.create_index('ix_users_status', 'users', ['status'])


def downgrade() -> None:
    op.drop_index('ix_users_status', table_name='users')
    op.drop_column('users', 'status')
