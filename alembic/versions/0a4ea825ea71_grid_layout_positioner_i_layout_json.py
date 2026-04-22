"""grid-layout-positioner-i-layout-json

Revision ID: 0a4ea825ea71
Revises: 818bfdce8784
Create Date: 2026-04-22 19:53:12.207356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a4ea825ea71'
down_revision: Union[str, None] = '818bfdce8784'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, layout_json FROM view")).fetchall()
    for row in rows:
        import json
        layout = json.loads(row.layout_json) if isinstance(row.layout_json, str) else (row.layout_json or {})
        widgets = layout.get("widgets", [])
        changed = False
        for i, w in enumerate(widgets):
            if "x" not in w:
                w["x"] = 0
                w["y"] = i * 6
                w["w"] = 12
                w["h"] = 6
                changed = True
        if changed:
            layout["widgets"] = widgets
            conn.execute(
                sa.text("UPDATE view SET layout_json = :j WHERE id = :id"),
                {"j": json.dumps(layout), "id": row.id},
            )


def downgrade() -> None:
    pass
