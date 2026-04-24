"""introducera-channel-lager

Revision ID: 0dd2cfcbe293
Revises: f5f235e32daf
Create Date: 2026-04-24 07:38:44.115938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0dd2cfcbe293'
down_revision: Union[str, None] = 'f5f235e32daf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Skapa channel-tabellen
    op.create_table(
        "channel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 3. Lägg till channel_id på screen
    with op.batch_alter_table("screen") as batch_op:
        batch_op.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))

    # 2. Skapa en kanal per befintlig skärm (samma namn) och koppla dem
    conn = op.get_bind()
    screens = conn.execute(sa.text("SELECT id, name FROM screen")).fetchall()
    for screen in screens:
        conn.execute(
            sa.text("INSERT INTO channel (name, description) VALUES (:name, '')"),
            {"name": screen.name}
        )
        # channel.id är nu ROWID = sist insatta rad i SQLite
        channel_id = conn.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        conn.execute(
            sa.text("UPDATE screen SET channel_id = :cid WHERE id = :sid"),
            {"cid": channel_id, "sid": screen.id}
        )

    # 4. Lägg till channel_id på screenlayoutassignment, migrera data, gör not null, drop screen_id
    with op.batch_alter_table("screenlayoutassignment") as batch_op:
        batch_op.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))
    
    conn.execute(sa.text("""
        UPDATE screenlayoutassignment SET channel_id = (
            SELECT channel_id FROM screen WHERE screen.id = screenlayoutassignment.screen_id
        )
    """))
    
    with op.batch_alter_table("screenlayoutassignment") as batch_op:
        batch_op.alter_column("channel_id", nullable=False)
        batch_op.drop_column("screen_id")

    # 5. Byt namn på tabellen
    op.rename_table("screenlayoutassignment", "channellayoutassignment")

    # 6. Lägg till channel_id på view, migrera data, gör not null, drop screen_id
    with op.batch_alter_table("view") as batch_op:
        batch_op.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))
    
    conn.execute(sa.text("""
        UPDATE view SET channel_id = (
            SELECT channel_id FROM screen WHERE screen.id = view.screen_id
        )
    """))
    
    with op.batch_alter_table("view") as batch_op:
        batch_op.alter_column("channel_id", nullable=False)
        batch_op.drop_column("screen_id")

    # 7. Lägg till channel_id på zonewidgetplacement, migrera data (nullable), drop screen_id
    with op.batch_alter_table("zonewidgetplacement") as batch_op:
        batch_op.add_column(sa.Column("channel_id", sa.Integer(), nullable=True))
    
    conn.execute(sa.text("""
        UPDATE zonewidgetplacement SET channel_id = (
            SELECT channel_id FROM screen WHERE screen.id = zonewidgetplacement.screen_id
        ) WHERE screen_id IS NOT NULL
    """))
    
    with op.batch_alter_table("zonewidgetplacement") as batch_op:
        batch_op.drop_column("screen_id")


def downgrade():
    pass  # nedgradering stöds inte
