"""rbac_and_global_chat

Revision ID: c3f1a8b2d9e0
Revises: 73b4533e59d4
Create Date: 2026-04-02 06:30:00.000000

Changes:
  - Add 'role' column to users table (default 'user')
  - Make chat_sessions.connection_id nullable (global chat)
  - Drop old index, create new user-based index
  - Seed hardcoded admin + regular user accounts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'c3f1a8b2d9e0'
down_revision: Union[str, Sequence[str], None] = '73b4533e59d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Add role column to users
    op.add_column('users', sa.Column('role', sa.String(), nullable=True))
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
    op.alter_column('users', 'role', nullable=False)

    # 2. Set admin role for the existing admin user (seeded at startup)
    op.execute("UPDATE users SET role = 'admin' WHERE email = 'admin@example.com'")

    # 3. Make chat_sessions.connection_id nullable (global chat)
    #    First drop the NOT NULL constraint and update FK to SET NULL on delete
    op.drop_index('ix_chat_sessions_tenant_connection', table_name='chat_sessions')
    op.drop_constraint('fk_chat_sessions_tenant_id_tenants', 'chat_sessions', type_='foreignkey')
    op.create_foreign_key(
        'fk_chat_sessions_tenant_id_tenants', 'chat_sessions', 'tenants',
        ['tenant_id'], ['id'], ondelete='CASCADE'
    )

    # Drop old connection FK and recreate with SET NULL
    # Find and drop the foreign key for connection_id
    op.execute("""
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT tc.constraint_name INTO fk_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'chat_sessions'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'connection_id';

            IF fk_name IS NOT NULL THEN
                EXECUTE 'ALTER TABLE chat_sessions DROP CONSTRAINT ' || quote_ident(fk_name);
            END IF;
        END $$;
    """)

    op.alter_column('chat_sessions', 'connection_id',
                    existing_type=sa.UUID(),
                    nullable=True)

    op.create_foreign_key(
        'fk_chat_sessions_connection_id', 'chat_sessions', 'db_connections',
        ['connection_id'], ['id'], ondelete='SET NULL'
    )

    # 4. Create new index on (tenant_id, user_id) instead of (tenant_id, connection_id)
    op.create_index('ix_chat_sessions_tenant_user', 'chat_sessions', ['tenant_id', 'user_id'], unique=False)

    # 5. Seed hardcoded users (admin@admin.local and user@user.local)
    #    Passwords are bcrypt hashes of "admin123" and "user123"
    #    We use a safe INSERT that skips if already exists
    op.execute("""
        DO $$
        DECLARE
            default_tenant_id UUID;
        BEGIN
            -- Get the first tenant or create one
            SELECT id INTO default_tenant_id FROM tenants LIMIT 1;

            IF default_tenant_id IS NULL THEN
                INSERT INTO tenants (id, name, created_at)
                VALUES (gen_random_uuid(), 'Default', NOW())
                RETURNING id INTO default_tenant_id;
            END IF;

            -- Seed admin user (password: admin123)
            INSERT INTO users (id, tenant_id, name, email, password_hash, role, is_active, created_at)
            VALUES (
                gen_random_uuid(),
                default_tenant_id,
                'Admin',
                'admin@admin.local',
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4oiHV.5gy6',
                'admin',
                true,
                NOW()
            )
            ON CONFLICT (email) DO UPDATE SET role = 'admin';

            -- Seed regular user (password: user123)
            INSERT INTO users (id, tenant_id, name, email, password_hash, role, is_active, created_at)
            VALUES (
                gen_random_uuid(),
                default_tenant_id,
                'User',
                'user@user.local',
                '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uBlmle/Je',
                'user',
                true,
                NOW()
            )
            ON CONFLICT (email) DO UPDATE SET role = 'user';
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chat_sessions_tenant_user', table_name='chat_sessions')
    op.drop_constraint('fk_chat_sessions_connection_id', 'chat_sessions', type_='foreignkey')

    op.alter_column('chat_sessions', 'connection_id',
                    existing_type=sa.UUID(),
                    nullable=False)

    op.create_foreign_key(
        None, 'chat_sessions', 'db_connections',
        ['connection_id'], ['id'], ondelete='CASCADE'
    )

    op.create_index('ix_chat_sessions_tenant_connection', 'chat_sessions', ['tenant_id', 'connection_id'], unique=False)

    op.drop_column('users', 'role')

    # Remove seeded users
    op.execute("DELETE FROM users WHERE email IN ('admin@admin.local', 'user@user.local')")
