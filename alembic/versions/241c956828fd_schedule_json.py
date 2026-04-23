"""schedule_json

Revision ID: 241c956828fd
Revises: 412f6a8d58d1
Create Date: 2026-04-23 19:51:19.137244

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '241c956828fd'
down_revision: Union[str, None] = '412f6a8d58d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns
    with op.batch_alter_table('view') as batch_op:
        batch_op.add_column(sa.Column('schedule_json', sa.JSON(), nullable=True))
    
    with op.batch_alter_table('screenlayoutassignment') as batch_op:
        batch_op.add_column(sa.Column('schedule_json', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('transition', sa.String(), nullable=False, server_default='fade'))
        batch_op.add_column(sa.Column('transition_duration_ms', sa.Integer(), nullable=False, server_default='700'))

    # 2. Data migration
    connection = op.get_bind()
    
    # View
    views = connection.execute(sa.text("SELECT id, schedule_weekdays, schedule_time_start, schedule_time_end FROM view")).fetchall()
    for row in views:
        v_id, v_weekdays, v_start, v_end = row
        if v_weekdays or v_start or v_end:
            sched = {"type": "weekly"}
            if v_weekdays: 
                sched["weekdays"] = [d.strip() for d in v_weekdays.split(',') if d.strip()]
            if v_start: 
                sched["time_start"] = v_start
            if v_end: 
                sched["time_end"] = v_end
            
            connection.execute(
                sa.text("UPDATE view SET schedule_json = :js WHERE id = :id"),
                {"js": json.dumps(sched), "id": v_id}
            )

    # ScreenLayoutAssignment
    assignments = connection.execute(sa.text("SELECT id, weekdays, time_start, time_end FROM screenlayoutassignment")).fetchall()
    for row in assignments:
        a_id, a_weekdays, a_start, a_end = row
        if a_weekdays or a_start or a_end:
            sched = {"type": "weekly"}
            if a_weekdays: 
                sched["weekdays"] = [d.strip() for d in a_weekdays.split(',') if d.strip()]
            if a_start: 
                sched["time_start"] = a_start
            if a_end: 
                sched["time_end"] = a_end
            
            connection.execute(
                sa.text("UPDATE screenlayoutassignment SET schedule_json = :js WHERE id = :id"),
                {"js": json.dumps(sched), "id": a_id}
            )

    # 3. Remove old columns
    with op.batch_alter_table('view') as batch_op:
        batch_op.drop_column('schedule_weekdays')
        batch_op.drop_column('schedule_time_start')
        batch_op.drop_column('schedule_time_end')
        
    with op.batch_alter_table('screenlayoutassignment') as batch_op:
        batch_op.drop_column('weekdays')
        batch_op.drop_column('time_start')
        batch_op.drop_column('time_end')


def downgrade() -> None:
    # 1. Add old columns back
    with op.batch_alter_table('view') as batch_op:
        batch_op.add_column(sa.Column('schedule_weekdays', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('schedule_time_start', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('schedule_time_end', sa.String(), nullable=True))
        
    with op.batch_alter_table('screenlayoutassignment') as batch_op:
        batch_op.add_column(sa.Column('weekdays', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('time_start', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('time_end', sa.String(), nullable=True))

    # 2. Reverse data migration
    connection = op.get_bind()
    
    # View
    views = connection.execute(sa.text("SELECT id, schedule_json FROM view")).fetchall()
    for row in views:
        v_id, v_js = row
        if v_js:
            try:
                if isinstance(v_js, str):
                    sched = json.loads(v_js)
                else:
                    sched = v_js
                
                if sched.get("type") == "weekly":
                    weekdays = ",".join(sched.get("weekdays", []))
                    connection.execute(
                        sa.text("UPDATE view SET schedule_weekdays = :w, schedule_time_start = :s, schedule_time_end = :e WHERE id = :id"),
                        {"w": weekdays or None, "s": sched.get("time_start"), "e": sched.get("time_end"), "id": v_id}
                    )
            except:
                pass

    # ScreenLayoutAssignment
    assignments = connection.execute(sa.text("SELECT id, schedule_json FROM screenlayoutassignment")).fetchall()
    for row in assignments:
        a_id, a_js = row
        if a_js:
            try:
                if isinstance(a_js, str):
                    sched = json.loads(a_js)
                else:
                    sched = a_js
                
                if sched.get("type") == "weekly":
                    weekdays = ",".join(sched.get("weekdays", []))
                    connection.execute(
                        sa.text("UPDATE screenlayoutassignment SET weekdays = :w, time_start = :s, time_end = :e WHERE id = :id"),
                        {"w": weekdays or None, "s": sched.get("time_start"), "e": sched.get("time_end"), "id": a_id}
                    )
            except:
                pass

    # 3. Remove new columns
    with op.batch_alter_table('view') as batch_op:
        batch_op.drop_column('schedule_json')
        
    with op.batch_alter_table('screenlayoutassignment') as batch_op:
        batch_op.drop_column('schedule_json')
        batch_op.drop_column('transition')
        batch_op.drop_column('transition_duration_ms')
