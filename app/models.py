from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel


class Screen(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    performance_mode: str = "normal"
    last_seen_at: datetime | None = None
    last_connection_count: int = 0
    alert_sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class View(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    screen_id: int = Field(foreign_key="screen.id")
    zone_id: int | None = Field(default=None, foreign_key="layoutzone.id")
    position: int
    name: str
    duration_seconds: int | None = None
    grid_cols: int = 12
    grid_rows: int = 9
    layout_json: Any = Field(default_factory=dict, sa_column=Column(JSON))
    schedule_weekdays: str | None = None   # t.ex. 'mon,tue,wed,thu,fri' eller None = alltid aktiv
    schedule_time_start: str | None = None  # 'HH:MM' eller None
    schedule_time_end: str | None = None    # 'HH:MM' eller None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Widget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str  # ics_list | ics_month | markdown | slideshow | iframe | clock | raw_html | debug
    name: str
    config_json: Any = Field(default_factory=dict, sa_column=Column(JSON))
    edit_token: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IcsCache(SQLModel, table=True):
    widget_id: int = Field(foreign_key="widget.id", primary_key=True)
    source_url: str = Field(primary_key=True)
    raw_ics: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    etag: str | None = None
    last_error: str | None = None


class WidgetRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    widget_id: int = Field(foreign_key="widget.id")
    config_json: Any = Field(default_factory=dict, sa_column=Column(JSON))
    name_at_save: str
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    saved_via: str  # "admin" | "edit_token"
    editor_ip: str | None = None
    editor_user_agent: str | None = None


class MediaFolder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    parent_id: int | None = Field(default=None, foreign_key="mediafolder.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MediaFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(unique=True, index=True)  # UUID-baserat filnamn på disk
    original_name: str
    content_type: str
    size_bytes: int
    folder_id: int | None = Field(default=None, foreign_key="mediafolder.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ViewSchedule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    view_id: int = Field(foreign_key="view.id")
    cron_expression: str
    duration_hours: int
    name: str
    enabled: bool = True


class Layout(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    aspect_ratio: str = "16:9"  # "16:9" | "9:16" | "4:3" etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LayoutZone(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    layout_id: int = Field(foreign_key="layout.id")
    name: str
    role: str = "schedulable"  # "persistent" | "schedulable"
    x_pct: float = 0.0  # 0–100 % av skärmbredden
    y_pct: float = 0.0  # 0–100 % av skärmhöjden
    w_pct: float = 100.0
    h_pct: float = 100.0
    grid_cols: int = 12
    grid_rows: int = 9
    z_index: int = 0
    rotation_seconds: int = 30
    transition: str = "fade"
    transition_direction: str = "left"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LayoutRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    layout_id: int = Field(foreign_key="layout.id")
    zones_json: Any = Field(default_factory=list, sa_column=Column(JSON))
    saved_at: datetime = Field(default_factory=datetime.utcnow)


class ZoneWidgetPlacement(SQLModel, table=True):
    """Widget-placering i en zon. screen_id=None → template-default; screen_id satt → skärm-override."""

    id: int | None = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="layoutzone.id")
    screen_id: int | None = Field(default=None, foreign_key="screen.id")
    # Biblioteks-widget (None om inline)
    widget_id: int | None = Field(default=None, foreign_key="widget.id")
    # Inline-widget (None om biblioteks-widget)
    inline_kind: str | None = None
    # Position inom zonen (grid-enheter)
    x: int = 0
    y: int = 0
    w: int = 4
    h: int = 4
    z_index: int = 0
    opacity: int = 100
    config_json: Any = Field(default_factory=dict, sa_column=Column(JSON))


class ScreenLayoutAssignment(SQLModel, table=True):
    """Kopplar en skärm till en layout, med valfritt tidschema."""

    id: int | None = Field(default=None, primary_key=True)
    screen_id: int = Field(foreign_key="screen.id")
    layout_id: int = Field(foreign_key="layout.id")
    priority: int = 0  # högre = testas först vid schemaläggning
    # Schemaläggning (None = alltid aktiv)
    weekdays: str | None = None  # t.ex. "mon,tue,wed,thu,fri"
    time_start: str | None = None  # "HH:MM"
    time_end: str | None = None  # "HH:MM"
    created_at: datetime = Field(default_factory=datetime.utcnow)
