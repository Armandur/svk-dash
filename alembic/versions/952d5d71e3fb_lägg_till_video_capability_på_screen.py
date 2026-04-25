"""lägg till video_capability på screen

Revision ID: 952d5d71e3fb
Revises: 392fa0879372
Create Date: 2026-04-25 11:51:40.606257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '952d5d71e3fb'
down_revision: Union[str, None] = '392fa0879372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('screen', schema=None) as batch_op:
        batch_op.add_column(sa.Column('video_capability', sa.String(),
                                       nullable=False, server_default='single'))


def downgrade() -> None:
    with op.batch_alter_table('screen', schema=None) as batch_op:
        batch_op.drop_column('video_capability')
