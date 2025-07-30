"""add_tags_column_to_notes_table

Revision ID: cf95497aa948
Revises: 47fd33329cc7
Create Date: 2025-06-27 10:54:57.753498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf95497aa948'
down_revision: Union[str, None] = '47fd33329cc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tags column to notes table
    op.add_column('notes', sa.Column('tags', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove tags column from notes table
    op.drop_column('notes', 'tags')
