"""add dashboards and dashboard_widgets tables

Revision ID: b1c2d3e4f5a6
Revises: f3e123abc456
Create Date: 2026-04-15 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f3e123abc456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dashboards',
        sa.Column('id',            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',       postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id',         ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('tenant_id',     postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id',       ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('db_connections.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name',          sa.String(),  nullable=False),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',    sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'dashboard_widgets',
        sa.Column('id',             postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dashboard_id',   postgresql.UUID(as_uuid=True), sa.ForeignKey('dashboards.id',    ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('saved_query_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('saved_queries.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title',          sa.String(),  nullable=False, server_default='Widget'),
        sa.Column('chart_type',     sa.String(),  nullable=False, server_default='bar'),
        sa.Column('config',         postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('grid_x',         sa.Integer(), nullable=False, server_default='0'),
        sa.Column('grid_y',         sa.Integer(), nullable=False, server_default='0'),
        sa.Column('grid_w',         sa.Integer(), nullable=False, server_default='6'),
        sa.Column('grid_h',         sa.Integer(), nullable=False, server_default='4'),
        sa.Column('created_at',     sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',     sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('dashboard_widgets')
    op.drop_table('dashboards')
