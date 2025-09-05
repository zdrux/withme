"""add timezone to agents

Revision ID: 1f2a3b4c5d6e
Revises: cafc6ef04c3c
Create Date: 2025-09-05 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f2a3b4c5d6e'
down_revision = 'cafc6ef04c3c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('timezone', sa.String(), server_default='UTC', nullable=False))
    # Optionally drop server_default after backfill
    op.alter_column('agents', 'timezone', server_default=None)


def downgrade() -> None:
    op.drop_column('agents', 'timezone')

