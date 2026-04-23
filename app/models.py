from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel


class Screen(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    rotation_seconds: int = 30
    aspect_ratio: str = "16:9"
    transition: str = "fade"
    performance_mode: str = "normal"
    last_seen_at: datetime | None = None
    last_connection_count: int = 0
    alert_sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class View(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    screen_id: int = Field(foreign_key="screen.id")
    position: int
    name: str
    duration_seconds: int | None = None
    grid_cols: int = 12
    grid_rows: int = 9
    layout_json: Any = Field(default_factory=dict, sa_column=Column(JSON))
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


class ViewSchedule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    view_id: int = Field(foreign_key="view.id")
    cron_expression: str
    duration_hours: int
    name: str
    enabled: bool = True
