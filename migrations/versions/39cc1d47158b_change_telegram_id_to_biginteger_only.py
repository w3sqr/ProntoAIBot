"""Change telegram_id to BigInteger only

Revision ID: 39cc1d47158b
Revises: 0d5ab7ec066b
Create Date: 2025-07-05 17:25:49.715019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39cc1d47158b'
down_revision: Union[str, None] = '0d5ab7ec066b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change telegram_id column from Integer to BigInteger
    op.alter_column('users', 'telegram_id',
               existing_type=sa.Integer(),
               type_=sa.BigInteger(),
               existing_nullable=False)


def downgrade() -> None:
    # Change telegram_id column back from BigInteger to Integer
    op.alter_column('users', 'telegram_id',
               existing_type=sa.BigInteger(),
               type_=sa.Integer(),
               existing_nullable=False)
