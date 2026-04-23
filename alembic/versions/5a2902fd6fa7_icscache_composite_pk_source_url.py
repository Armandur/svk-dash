"""icscache_composite_pk_source_url

Revision ID: 5a2902fd6fa7
Revises: edf19cd3708f
Create Date: 2026-04-23 06:59:03.371159

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5a2902fd6fa7"
down_revision: Union[str, None] = "edf19cd3708f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("icscache", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(), nullable=False, server_default=""))
        batch_op.create_primary_key("pk_icscache", ["widget_id", "source_url"])


def downgrade() -> None:
    with op.batch_alter_table("icscache", recreate="always") as batch_op:
        batch_op.drop_column("source_url")
        batch_op.create_primary_key("pk_icscache", ["widget_id"])
