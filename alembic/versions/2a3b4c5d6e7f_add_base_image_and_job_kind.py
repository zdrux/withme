"""add base image url and image job kind

Revision ID: 2a3b4c5d6e7f
Revises: 1f2a3b4c5d6e
Create Date: 2025-09-05 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '2a3b4c5d6e7f'
down_revision = '1f2a3b4c5d6e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('base_image_url', sa.Text(), nullable=True))
    op.add_column('image_jobs', sa.Column('kind', sa.String(), nullable=True))
    op.create_check_constraint('ck_image_jobs_kind', 'image_jobs', "kind is null or kind in ('base','gen','edit')")


def downgrade() -> None:
    op.drop_constraint('ck_image_jobs_kind', 'image_jobs')
    op.drop_column('image_jobs', 'kind')
    op.drop_column('agents', 'base_image_url')

