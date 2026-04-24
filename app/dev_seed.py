"""
Testdata för utveckling. Aktiveras med DEV_SEED=true i miljön.
Rensar databasen och skapar kanaler, layouts, widgets och vyer.
"""
import logging
import os
import secrets

from sqlmodel import SQLModel

from app.database import engine, get_session
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

_UPLOADS = "data/uploads"

# Kända testbilder (UUID-filnamn → originalnamn)
_SEED_IMAGES = [
    ("965e2a37f00246c4a624aa8162d43cd9.jpg", "tall.jpg"),      # porträtt
    ("161892b4d3134a0da1fa4c77b762a1b1.jpg", "blabar.jpg"),    # liggande
    ("2e2a9ce34b544eee910e997b59e0052a.jpg", "talt20.jpg"),    # liggande
]


def _widget(name, kind, config, **kw) -> Widget:
    return Widget(name=name, kind=kind, config_json=config,
                  edit_token=secrets.token_urlsafe(32), **kw)


def _label(text: str) -> Widget:
    """Liten etikett-overlay för att identifiera widget i vyerna."""
    return _widget(
        f"[etikett] {text}", "text",
        {
            "text": text,
            "font_size": "1.6cqh",
            "text_color": "#ffffff",
            "text_align": "left",
            "bg_color": "rgba(0,0,0,0.6)",
            "padding": "0.3em 0.7em",
            "italic": True,
        },
    )


def _lbl_row(wid: Widget, label: Widget) -> list[dict]:
    """Placera widget fullskärm (z_index=0) + etikett i sista raden (z_index=10)."""
    return [
        {"widget_id": wid.id,   "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
        {"widget_id": label.id, "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
    ]


def seed() -> None:
    log.warning("DEV_SEED=true — rensar och återskapar databas med testdata")

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with get_session() as db:

        # ── Mediafiler ────────────────────────────────────────────────────────
        media: dict[str, MediaFile] = {}
        for uuid_name, orig_name in _SEED_IMAGES:
            path = os.path.join(_UPLOADS, uuid_name)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            mf = MediaFile(filename=uuid_name, original_name=orig_name,
                           content_type="image/jpeg", size_bytes=size)
            db.add(mf)
            media[orig_name] = mf
        db.flush()

        # ── Layouts ───────────────────────────────────────────────────────────
        l_land_split = Layout(name="Landskap 60/40", aspect_ratio="16:9")
        l_land_full  = Layout(name="Landskap fullskärm", aspect_ratio="16:9")
        l_land_bar   = Layout(name="Landskap huvud + sidfält", aspect_ratio="16:9")
        l_port_full  = Layout(name="Porträtt fullskärm", aspect_ratio="9:16")
        db.add_all([l_land_split, l_land_full, l_land_bar, l_port_full])
        db.flush()

        # Zoner
        z_split_left = LayoutZone(
            layout_id=l_land_split.id, name="Vänster", role="schedulable",
            x_pct=0, y_pct=0, w_pct=60, h_pct=100, rotation_seconds=12,
            transition="slide", transition_direction="left",
        )
        z_split_right = LayoutZone(
            layout_id=l_land_split.id, name="Höger", role="schedulable",
            x_pct=60, y_pct=0, w_pct=40, h_pct=100, rotation_seconds=10,
            transition="fade",
        )
        z_full_main = LayoutZone(
            layout_id=l_land_full.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=10,
            transition="fade",
        )
        z_bar_main = LayoutZone(
            layout_id=l_land_bar.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=75, h_pct=100, rotation_seconds=12,
            transition="slide", transition_direction="up",
        )
        z_bar_side = LayoutZone(
            layout_id=l_land_bar.id, name="Sidfält", role="persistent",
            x_pct=75, y_pct=0, w_pct=25, h_pct=100, rotation_seconds=0,
        )
        z_port_main = LayoutZone(
            layout_id=l_port_full.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=10,
            transition="slide", transition_direction="up",
        )
        db.add_all([z_split_left, z_split_right, z_full_main,
                    z_bar_main, z_bar_side, z_port_main])
        db.flush()

        # ── Widgets ───────────────────────────────────────────────────────────

        # Klocka/datum – tre varianter
        w_clock_td = _widget("Klocka tid+datum", "clock", {
            "format": "time_date", "timezone": "Europe/Stockholm",
            "font_size": "9cqh", "text_color": "#ffffff",
            "show_seconds": True,
        })
        w_clock_t = _widget("Klocka enbart tid", "clock", {
            "format": "time_only", "timezone": "Europe/Stockholm",
            "font_size": "14cqh", "text_color": "#f0c060",
            "show_seconds": False,
        })
        w_clock_12h = _widget("Klocka 12h (AM/PM)", "clock", {
            "format": "time_date", "timezone": "Europe/Stockholm",
            "font_size": "9cqh", "text_color": "#ffffff",
            "hour12": True, "show_seconds": False,
            "date_format": "%A %-d %B",
        })
        w_clock_day = _widget("Klocka dag+tid", "clock", {
            "format": "day_time", "timezone": "Europe/Stockholm",
            "font_size": "10cqh", "text_color": "#ffffff",
        })

        # Text – tre varianter
        w_text_normal = _widget("Text – normal", "text", {
            "text": "Informationsskärm", "font_size": "5cqh",
            "text_color": "#ffffff", "text_align": "center",
        })
        w_text_styled = _widget("Text – fet+versaler+spatiering", "text", {
            "text": "Välkommen hit", "font_size": "5cqh",
            "text_color": "#c8a85a", "text_align": "center",
            "bold": True, "uppercase": True, "letter_spacing": "0.2em",
        })
        w_text_italic = _widget("Text – kursiv", "text", {
            "text": "Välkommen till vår kyrka", "font_size": "4.5cqh",
            "text_color": "#ffffff", "text_align": "center",
            "italic": True,
        })

        # Färgblock – solid och gradient
        w_color_solid = _widget("Färgblock – mörkblå", "color_block", {
            "bg_color": "#1e3a5f",
        })
        w_color_gradient = _widget("Färgblock – gradient", "color_block", {
            "use_gradient": True, "gradient_start": "#1e3a5f",
            "gradient_end": "#000000", "gradient_angle": 135,
            "border_radius": 0,
        })
        w_color_gold = _widget("Färgblock – guld→mörkblå", "color_block", {
            "use_gradient": True, "gradient_start": "#c8a85a",
            "gradient_end": "#1e3a5f", "gradient_angle": 180,
        })

        # Bild
        w_image = _widget("Bild – tall (porträtt, contain)", "image", {
            "upload_path": media["tall.jpg"].filename,
            "fit": "contain", "border_radius": 12,
        })
        w_image_blabar = _widget("Bild – blåbär (cover)", "image", {
            "upload_path": media["blabar.jpg"].filename,
            "fit": "cover",
        })

        # Bildspel
        w_slideshow = _widget("Bildspel – naturfoto", "slideshow", {
            "images": [
                {"upload_path": media["tall.jpg"].filename,   "caption": "Tall – porträttformat"},
                {"upload_path": media["blabar.jpg"].filename, "caption": "Blåbär i skogen"},
                {"upload_path": media["talt20.jpg"].filename, "caption": "Talt 20"},
            ],
            "interval": 5, "transition": "slide", "fit": "cover",
        })

        # Markdown
        w_md = _widget("Välkomsttext", "markdown", {
            "content_md": (
                "## Välkommen\n\n"
                "Detta är en **testvy** för att demonstrera markdown-widgeten.\n\n"
                "- Stöder *kursiv* och **fetstil**\n"
                "- Punktlistor och rubriker\n"
                "- Redigeras via delegerad URL"
            ),
            "font_size": "1.8cqh", "text_color": "#ffffff", "text_align": "left",
        })

        # Etiketter (overlay-text i varje vy)
        lbl_clock_td  = _label("Klocka – tid+datum")
        lbl_clock_t   = _label("Klocka – enbart tid (sekunder dolda)")
        lbl_clock_12h = _label("Klocka – 12h AM/PM, anpassat datumformat")
        lbl_clock_day = _label("Klocka – dag+tid")
        lbl_text_n    = _label("Text – normal")
        lbl_text_s    = _label("Text – fet, versaler, spatiering")
        lbl_text_i    = _label("Text – kursiv")
        lbl_color_sol = _label("Färgblock – solid")
        lbl_color_gr  = _label("Färgblock – gradient 135°")
        lbl_color_gd  = _label("Färgblock – gradient guld→blå")
        lbl_image     = _label("Bildwidget – contain, hörnradius 12px")
        lbl_image_bb  = _label("Bildwidget – blåbär, cover")
        lbl_slideshow = _label("Bildspel – slide-transition, 5s/bild")
        lbl_md        = _label("Markdown-widget")

        all_widgets = [
            w_clock_td, w_clock_t, w_clock_12h, w_clock_day,
            w_text_normal, w_text_styled, w_text_italic,
            w_color_solid, w_color_gradient, w_color_gold,
            w_image, w_image_blabar, w_slideshow, w_md,
            lbl_clock_td, lbl_clock_t, lbl_clock_12h, lbl_clock_day,
            lbl_text_n, lbl_text_s, lbl_text_i,
            lbl_color_sol, lbl_color_gr, lbl_color_gd,
            lbl_image, lbl_image_bb, lbl_slideshow, lbl_md,
        ]
        db.add_all(all_widgets)
        db.flush()

        # ── Kanaler ───────────────────────────────────────────────────────────
        ch_land = Channel(name="Demo landskap", aspect_ratio="16:9")
        ch_port = Channel(name="Demo porträtt", aspect_ratio="9:16")
        db.add_all([ch_land, ch_port])
        db.flush()

        # ── Skärmar ───────────────────────────────────────────────────────────
        s1 = Screen(name="Skärm landskap", slug="landscape-test", channel_id=ch_land.id)
        s2 = Screen(name="Skärm porträtt", slug="portrait-test",  channel_id=ch_port.id)
        db.add_all([s1, s2])
        db.flush()

        # ── Layout-tilldelningar (med transitions) ────────────────────────────
        # Landskap: 60/40-split är primär, fullskärm roterar in efter 25 s
        a_split = ChannelLayoutAssignment(
            channel_id=ch_land.id, layout_id=l_land_split.id,
            priority=0, duration_seconds=25,
            transition="slide", transition_direction="left",
        )
        a_full = ChannelLayoutAssignment(
            channel_id=ch_land.id, layout_id=l_land_full.id,
            priority=1, duration_seconds=20,
            transition="fade",
        )
        a_bar = ChannelLayoutAssignment(
            channel_id=ch_land.id, layout_id=l_land_bar.id,
            priority=2, duration_seconds=20,
            transition="slide", transition_direction="right",
        )
        a_port = ChannelLayoutAssignment(
            channel_id=ch_port.id, layout_id=l_port_full.id,
            priority=0,
        )
        db.add_all([a_split, a_full, a_bar, a_port])
        db.flush()

        def wl(*pairs) -> dict:
            """Bygg layout_json från (widget, label)-par + valfria extra."""
            widgets = []
            for w, lbl in pairs:
                widgets += _lbl_row(w, lbl)
            return {"widgets": widgets}

        def wl1(w, lbl) -> dict:
            return {"widgets": _lbl_row(w, lbl)}

        # ── Vyer – 60/40-split, vänster zon (slide left, 12 s) ───────────────
        views_split_left = [
            View(channel_id=ch_land.id, zone_id=z_split_left.id, position=0,
                 name="Klocka tid+datum", enabled=True, duration_seconds=12,
                 layout_json=wl1(w_clock_td, lbl_clock_td)),
            View(channel_id=ch_land.id, zone_id=z_split_left.id, position=1,
                 name="Klocka enbart tid", enabled=True, duration_seconds=10,
                 transition="slide", transition_direction="right",
                 layout_json=wl1(w_clock_t, lbl_clock_t)),
            View(channel_id=ch_land.id, zone_id=z_split_left.id, position=2,
                 name="Klocka 12h AM/PM", enabled=True, duration_seconds=10,
                 transition="fade",
                 layout_json=wl1(w_clock_12h, lbl_clock_12h)),
            View(channel_id=ch_land.id, zone_id=z_split_left.id, position=3,
                 name="Bildspel", enabled=True, duration_seconds=20,
                 transition="none",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_land.id, zone_id=z_split_left.id, position=4,
                 name="Markdown", enabled=True, duration_seconds=12,
                 transition="slide", transition_direction="up",
                 layout_json=wl1(w_md, lbl_md)),
        ]

        # ── Vyer – 60/40-split, höger zon (fade, 10 s) ───────────────────────
        views_split_right = [
            View(channel_id=ch_land.id, zone_id=z_split_right.id, position=0,
                 name="Färgblock gradient", enabled=True,
                 layout_json=wl1(w_color_gradient, lbl_color_gr)),
            View(channel_id=ch_land.id, zone_id=z_split_right.id, position=1,
                 name="Text versaler", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_styled.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_s.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_land.id, zone_id=z_split_right.id, position=2,
                 name="Text kursiv", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gold.id,  "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_italic.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_i.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]

        # ── Vyer – fullskärm (fade, 10 s) ────────────────────────────────────
        views_full = [
            View(channel_id=ch_land.id, zone_id=z_full_main.id, position=0,
                 name="Bild blåbär (cover)", enabled=True,
                 layout_json=wl1(w_image_blabar, lbl_image_bb)),
            View(channel_id=ch_land.id, zone_id=z_full_main.id, position=1,
                 name="Klocka dag+tid", enabled=True,
                 transition="slide", transition_direction="up",
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_day.id,      "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_day.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_land.id, zone_id=z_full_main.id, position=2,
                 name="Text normal", enabled=True, transition="none",
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id,  "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_normal.id,  "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_n.id,     "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]

        # ── Vyer – huvud+sidfält (slide up, 12 s) ────────────────────────────
        views_bar_main = [
            View(channel_id=ch_land.id, zone_id=z_bar_main.id, position=0,
                 name="Bildspel", enabled=True, duration_seconds=18,
                 transition="none",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_land.id, zone_id=z_bar_main.id, position=1,
                 name="Klocka tid+datum", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_td.id,       "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_td.id,     "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]
        # Sidfält (persistent): färgblock + centrerad text
        views_bar_side = [
            View(channel_id=ch_land.id, zone_id=z_bar_side.id, position=0,
                 name="Sidfält – klocka", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_t.id,     "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                 ]}),
        ]

        # ── Vyer – porträtt ───────────────────────────────────────────────────
        views_port = [
            View(channel_id=ch_port.id, zone_id=z_port_main.id, position=0,
                 name="Klocka tid+datum", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_td.id,       "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_td.id,     "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_port.id, zone_id=z_port_main.id, position=1,
                 name="Bild tall (contain)", enabled=True, transition="fade",
                 layout_json=wl1(w_image, lbl_image)),
            View(channel_id=ch_port.id, zone_id=z_port_main.id, position=2,
                 name="Bildspel", enabled=True, duration_seconds=20,
                 transition="slide", transition_direction="up",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_port.id, zone_id=z_port_main.id, position=3,
                 name="Text versaler", enabled=True,
                 transition="slide", transition_direction="left",
                 layout_json={"widgets": [
                     {"widget_id": w_color_gold.id,  "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_styled.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_s.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_port.id, zone_id=z_port_main.id, position=4,
                 name="Markdown", enabled=True, transition="none",
                 layout_json=wl1(w_md, lbl_md)),
        ]

        all_views = (views_split_left + views_split_right + views_full
                     + views_bar_main + views_bar_side + views_port)
        db.add_all(all_views)

        # ── Varumärkesfärger ─────────────────────────────────────────────────
        palette = [
            BrandColor(name="Mörkblå (primär)",       color="#1e3a5f",          position=0),
            BrandColor(name="Guld",                    color="#c8a85a",          position=1),
            BrandColor(name="Vit",                     color="#ffffff",          position=2),
            BrandColor(name="Svart",                   color="#000000",          position=3),
            BrandColor(name="Ljusgrå",                 color="#f5f5f5",          position=4),
            BrandColor(name="Mörkgrå",                 color="#333333",          position=5),
            BrandColor(name="Röd (varning)",           color="#c0392b",          position=6),
            BrandColor(name="Halvtransparent mörk",    color="rgba(0,0,0,0.55)", position=7),
        ]
        db.add_all(palette)
        db.commit()

    views_n = len(all_views)
    log.warning(
        "DEV_SEED klar: 2 kanaler, 2 skärmar (/s/landscape-test, /s/portrait-test), "
        "%d widgets, %d vyer, 3 mediafiler, 8 varumärkesfärger",
        len(all_widgets), views_n,
    )
