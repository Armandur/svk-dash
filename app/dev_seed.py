"""
Testdata för utveckling. Aktiveras med DEV_SEED=true i miljön.
Rensar databasen och skapar kanaler, layouts, widgets och vyer.
"""
import logging
import secrets

from sqlmodel import SQLModel

from app.database import engine, get_session
import os

from app.models import (
    BrandColor,
    Channel,
    ChannelLayoutAssignment,
    Layout,
    LayoutZone,
    MediaFile,
    Screen,
    View,
    Widget,
)

log = logging.getLogger(__name__)


def seed() -> None:
    log.warning("DEV_SEED=true — rensar och återskapar databas med testdata")

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with get_session() as db:
        # ── Layouts ───────────────────────────────────────────────────────────
        l_land = Layout(name="Landskap 1-zon", aspect_ratio="16:9")
        l_land2 = Layout(name="Landskap 2-zoner", aspect_ratio="16:9")
        l_port = Layout(name="Porträtt 1-zon", aspect_ratio="9:16")
        db.add_all([l_land, l_land2, l_port])
        db.flush()

        # Zoner – procent av layoutens yta
        z_land_full = LayoutZone(
            layout_id=l_land.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100,
            rotation_seconds=10,
        )
        z_land_left = LayoutZone(
            layout_id=l_land2.id, name="Vänster", role="schedulable",
            x_pct=0, y_pct=0, w_pct=60, h_pct=100,
            rotation_seconds=15,
        )
        z_land_right = LayoutZone(
            layout_id=l_land2.id, name="Höger", role="schedulable",
            x_pct=60, y_pct=0, w_pct=40, h_pct=100,
            rotation_seconds=0,
        )
        z_port_full = LayoutZone(
            layout_id=l_port.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100,
            rotation_seconds=10,
        )
        db.add_all([z_land_full, z_land_left, z_land_right, z_port_full])
        db.flush()

        # ── Mediafiler (pekar på redan uppladdade filer på disk) ─────────────
        _uploads = "data/uploads"
        _media = [
            ("965e2a37f00246c4a624aa8162d43cd9.jpg", "tall.jpg"),
            ("161892b4d3134a0da1fa4c77b762a1b1.jpg", "blabar.jpg"),
            ("2e2a9ce34b544eee910e997b59e0052a.jpg", "talt20.jpg"),
        ]
        media_objs = {}
        for uuid_name, orig_name in _media:
            path = os.path.join(_uploads, uuid_name)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            mf = MediaFile(filename=uuid_name, original_name=orig_name,
                           content_type="image/jpeg", size_bytes=size)
            db.add(mf)
            media_objs[orig_name] = mf
        db.flush()

        # ── Widgets ───────────────────────────────────────────────────────────
        w_clock = Widget(
            name="Klocka",
            kind="clock",
            config_json={"format": "time_date", "timezone": "Europe/Stockholm",
                         "font_size": "8cqh", "text_color": "#ffffff"},
            edit_token=secrets.token_urlsafe(32),
        )
        w_bg = Widget(
            name="Bakgrund blå",
            kind="color_block",
            config_json={"bg_color": "#1e3a5f"},
            edit_token=secrets.token_urlsafe(32),
        )
        w_md = Widget(
            name="Välkomsttext",
            kind="markdown",
            config_json={
                "content_md": "## Välkommen\n\nDetta är en testwidget.\n\n- Punkt ett\n- Punkt två",
                "font_size": "1.2rem",
                "text_color": "#ffffff",
                "text_align": "center",
            },
            edit_token=secrets.token_urlsafe(32),
        )
        w_text = Widget(
            name="Rubrik",
            kind="text",
            config_json={
                "text": "Testskärm",
                "bold": True,
                "text_color": "#ffffff",
                "font_size": "4cqh",
                "text_align": "center",
            },
            edit_token=secrets.token_urlsafe(32),
        )
        w_image = Widget(
            name="Tallbild (porträtt)",
            kind="image",
            config_json={
                "source": "upload",
                "filename": media_objs["tall.jpg"].filename,
                "object_fit": "contain",
                "border_radius": 0,
            },
            edit_token=secrets.token_urlsafe(32),
        )
        w_slideshow = Widget(
            name="Bildspel naturfoto",
            kind="slideshow",
            config_json={
                "images": [
                    {"filename": media_objs["tall.jpg"].filename,    "caption": "Tall – porträttformat"},
                    {"filename": media_objs["blabar.jpg"].filename,  "caption": "Blåbär"},
                    {"filename": media_objs["talt20.jpg"].filename,  "caption": "Talt 20"},
                ],
                "interval": 5,
                "transition": "fade",
                "object_fit": "cover",
            },
            edit_token=secrets.token_urlsafe(32),
        )
        db.add_all([w_clock, w_bg, w_md, w_text, w_image, w_slideshow])
        db.flush()

        # ── Kanaler ───────────────────────────────────────────────────────────
        ch_land = Channel(name="Landskap test", aspect_ratio="16:9")
        ch_port = Channel(name="Porträtt test", aspect_ratio="9:16")
        db.add_all([ch_land, ch_port])
        db.flush()

        # ── Skärmar ───────────────────────────────────────────────────────────
        s1 = Screen(name="Skärm landskap", slug="first", channel_id=ch_land.id)
        s2 = Screen(name="Skärm porträtt", slug="second", channel_id=ch_port.id)
        db.add_all([s1, s2])
        db.flush()

        # ── Layout-tilldelningar ──────────────────────────────────────────────
        a_land = ChannelLayoutAssignment(
            channel_id=ch_land.id, layout_id=l_land2.id, priority=0,
        )
        a_port = ChannelLayoutAssignment(
            channel_id=ch_port.id, layout_id=l_port.id, priority=0,
        )
        db.add_all([a_land, a_port])
        db.flush()

        # ── Vyer ─────────────────────────────────────────────────────────────
        # Landskap vänster zon: klocka + markdown (roterar)
        v1 = View(
            channel_id=ch_land.id, zone_id=z_land_left.id, position=0,
            name="Klocka", enabled=True,
            layout_json={"widgets": [{"widget_id": w_clock.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        v2 = View(
            channel_id=ch_land.id, zone_id=z_land_left.id, position=1,
            name="Välkomsttext", enabled=True,
            layout_json={"widgets": [{"widget_id": w_md.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        # Landskap höger zon: bakgrund + rubrik
        v3 = View(
            channel_id=ch_land.id, zone_id=z_land_right.id, position=0,
            name="Rubrik", enabled=True,
            layout_json={"widgets": [
                {"widget_id": w_bg.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0},
                {"widget_id": w_text.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 1},
            ]},
        )
        # Porträtt zon: klocka + markdown
        v4 = View(
            channel_id=ch_port.id, zone_id=z_port_full.id, position=0,
            name="Klocka", enabled=True,
            layout_json={"widgets": [{"widget_id": w_clock.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        v5 = View(
            channel_id=ch_port.id, zone_id=z_port_full.id, position=1,
            name="Info", enabled=True,
            layout_json={"widgets": [{"widget_id": w_md.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        v6 = View(
            channel_id=ch_land.id, zone_id=z_land_left.id, position=2,
            name="Bildspel", enabled=True,
            layout_json={"widgets": [{"widget_id": w_slideshow.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        v7 = View(
            channel_id=ch_port.id, zone_id=z_port_full.id, position=2,
            name="Tallbild", enabled=True,
            layout_json={"widgets": [{"widget_id": w_image.id, "x": 0, "y": 0, "w": 100, "h": 100, "z": 0}]},
        )
        db.add_all([v1, v2, v3, v4, v5, v6, v7])

        # ── Varumärkesfärger ─────────────────────────────────────────────────
        palette = [
            BrandColor(name="Mörkblå (primär)",  color="#1e3a5f", position=0),
            BrandColor(name="Guld",               color="#c8a85a", position=1),
            BrandColor(name="Vit",                color="#ffffff", position=2),
            BrandColor(name="Svart",              color="#000000", position=3),
            BrandColor(name="Ljusgrå",            color="#f5f5f5", position=4),
            BrandColor(name="Mörkgrå",            color="#333333", position=5),
            BrandColor(name="Röd (varning)",      color="#c0392b", position=6),
            BrandColor(name="Halvtransparent mörk", color="rgba(0,0,0,0.55)", position=7),
        ]
        db.add_all(palette)
        db.commit()

    log.warning("DEV_SEED klar: 2 kanaler, 2 skärmar (/s/first, /s/second), 6 widgets, 3 mediafiler, 8 varumärkesfärger")
