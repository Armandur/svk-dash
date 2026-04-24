from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel


class Channel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    aspect_ratio: str = "16:9"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Screen(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    channel_id: int | None = Field(default=None, foreign_key="channel.id")
    performance_mode: str = "normal"
    last_seen_at: datetime | None = None
    last_connection_count: int = 0
    expected_connections: int = Field(default=1)
    show_offline_banner: bool = True
    alert_sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class View(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    channel_id: int = Field(foreign_key="channel.id")
    zone_id: int | None = Field(default=None, foreign_key="layoutzone.id")
    position: int
    name: str
    enabled: bool = True
    duration_seconds: int | None = None
    transition: str | None = None           # None = ärv från zon
    transition_direction: str | None = None
    transition_duration_ms: int | None = None
    grid_cols: int = 12
    grid_rows: int = 9
    layout_json: Any = Field(default_factory=dict, sa_column=Column(JSON))
    schedule_json: Any = Field(default=None, sa_column=Column(JSON))
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
    transition_duration_ms: int = 700
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LayoutRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    layout_id: int = Field(foreign_key="layout.id")
    zones_json: Any = Field(default_factory=list, sa_column=Column(JSON))
    saved_at: datetime = Field(default_factory=datetime.utcnow)


class ZoneWidgetPlacement(SQLModel, table=True):
    """Widget-placering i en zon. channel_id=None → template-default; channel_id satt → kanal-override."""

    id: int | None = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="layoutzone.id")
    channel_id: int | None = Field(default=None, foreign_key="channel.id")
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


class ChannelLayoutAssignment(SQLModel, table=True):
    """Kopplar en kanal till en layout, med valfritt tidschema."""

    id: int | None = Field(default=None, primary_key=True)
    channel_id: int = Field(foreign_key="channel.id")
    layout_id: int = Field(foreign_key="layout.id")
    priority: int = 0
    enabled: bool = True
    schedule_json: Any = Field(default=None, sa_column=Column(JSON))
    duration_seconds: int | None = None
    transition: str = "fade"
    transition_direction: str = "left"
    transition_duration_ms: int = 700
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BrandColor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    color: str  # hex (#rrggbb) eller rgba(r,g,b,a)
    position: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    screen_id: int | None = Field(default=None, foreign_key="screen.id", ondelete="SET NULL")
    screen_name: str                          # snapshot av skärmnamnet
    kind: str = "screen_offline"
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    seen_at: datetime | None = None
