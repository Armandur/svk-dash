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
    AppSetting,
    BrandColor,
    Channel,
    ChannelLayoutAssignment,
    IcsCache,
    Layout,
    LayoutZone,
    MediaFile,
    Screen,
    View,
    Widget,
)
from app.routes.dev_cal import DEV_CAL_URL, generate_ics

log = logging.getLogger(__name__)

_UPLOADS = "data/uploads"

# Kända testbilder (UUID-filnamn → originalnamn)
_SEED_IMAGES = [
    ("965e2a37f00246c4a624aa8162d43cd9.jpg", "tall.jpg"),      # porträtt
    ("161892b4d3134a0da1fa4c77b762a1b1.jpg", "blabar.jpg"),    # liggande
    ("2e2a9ce34b544eee910e997b59e0052a.jpg", "talt20.jpg"),    # liggande
]

_SEED_VIDEOS = [
    ("564c6a18466f4b57905cb8bc9d7bd7d8.mp4", "drone.mp4"),    # landskap
    ("9b319073423e4656b44922df7e35be53.mp4",  "murana.mp4"),  # landskap
    ("8cd61deee6aa4b0388ff367c5ccda8a2.mp4",  "fagel.mp4"),   # landskap
    ("6c54d7b48ef74eec85f029b888f5c642.mp4",  "snow.mp4"),    # porträtt
    # 720p-varianter (1.5 Mbps) för RPi 4B 1 GB där mjukvarudekod av 1080p laggar
    ("4498d01c7964409e8f1d88455a35b157.mp4", "drone_720.mp4"),
    ("da1cf31d12d94b54ac8ceea992e93815.mp4", "murana_720.mp4"),
    ("ddc8a04cc1f447f8a040d35cb834f890.mp4", "fagel_720.mp4"),
    ("ec9114811c16452eb1a2a64a650b3e4b.mp4", "snow_720.mp4"),
]

_SEED_PDFS = [
    ("5a4f48f98b5a4316a1078a17d64fe1c4.pdf", "medlem.pdf"),
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
        for uuid_name, orig_name in _SEED_VIDEOS:
            path = os.path.join(_UPLOADS, uuid_name)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            mf = MediaFile(filename=uuid_name, original_name=orig_name,
                           content_type="video/mp4", size_bytes=size)
            db.add(mf)
            media[orig_name] = mf
        for uuid_name, orig_name in _SEED_PDFS:
            path = os.path.join(_UPLOADS, uuid_name)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            mf = MediaFile(filename=uuid_name, original_name=orig_name,
                           content_type="application/pdf", size_bytes=size)
            db.add(mf)
            media[orig_name] = mf
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

        # ICS-kalenderwidgets
        _ics_cfg = {"ics_url": DEV_CAL_URL, "timezone": "Europe/Stockholm"}
        w_ics_list = _widget("Kalender – lista", "ics_list", {
            **_ics_cfg, "days_ahead": 14, "show_location": True,
            "group_by_day": True, "show_time": True,
        })
        w_ics_week = _widget("Kalender – vecka", "ics_week", {**_ics_cfg})
        w_ics_month = _widget("Kalender – månad", "ics_month", {**_ics_cfg})
        w_ics_schedule = _widget("Kalender – schema", "ics_schedule", {**_ics_cfg})

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
        lbl_slideshow   = _label("Bildspel – slide-transition, 5s/bild")
        lbl_md          = _label("Markdown-widget")
        lbl_ics_list    = _label("Kalender – lista (14 dagar)")
        lbl_ics_week    = _label("Kalender – veckoöversikt")
        lbl_ics_month   = _label("Kalender – månadsvy")
        lbl_ics_schedule = _label("Kalender – dagens schema")

        w_pdf_medlem = _widget("PDF – Medlemsinfo", "pdf", {"upload_path": media["medlem.pdf"].filename})
        lbl_pdf_medlem = _label("PDF – Medlemsinfo")

        _vid_cfg = {"loop": True, "muted": True, "fit": "cover"}
        w_video_drone  = _widget("Video – drone",  "video", {**_vid_cfg, "upload_path": media["drone.mp4"].filename})
        w_video_murana = _widget("Video – murana", "video", {**_vid_cfg, "upload_path": media["murana.mp4"].filename})
        w_video_fagel  = _widget("Video – fågel",  "video", {**_vid_cfg, "upload_path": media["fagel.mp4"].filename})
        w_video_snow   = _widget("Video – snö",    "video", {**_vid_cfg, "upload_path": media["snow.mp4"].filename})
        lbl_video_drone  = _label("Video – drone (landskap)")
        lbl_video_murana = _label("Video – murana (landskap)")
        lbl_video_fagel  = _label("Video – fågel (landskap)")
        lbl_video_snow   = _label("Video – snö (porträtt)")

        # 720p-varianter
        w_video_drone_720  = _widget("Video – drone (720p)",  "video", {**_vid_cfg, "upload_path": media["drone_720.mp4"].filename})
        w_video_murana_720 = _widget("Video – murana (720p)", "video", {**_vid_cfg, "upload_path": media["murana_720.mp4"].filename})
        w_video_fagel_720  = _widget("Video – fågel (720p)",  "video", {**_vid_cfg, "upload_path": media["fagel_720.mp4"].filename})
        w_video_snow_720   = _widget("Video – snö (720p)",    "video", {**_vid_cfg, "upload_path": media["snow_720.mp4"].filename})
        lbl_video_drone_720  = _label("Video – drone 720p")
        lbl_video_murana_720 = _label("Video – murana 720p")
        lbl_video_fagel_720  = _label("Video – fågel 720p")
        lbl_video_snow_720   = _label("Video – snö 720p")

        all_widgets = [
            w_clock_td, w_clock_t, w_clock_12h, w_clock_day,
            w_text_normal, w_text_styled, w_text_italic,
            w_color_solid, w_color_gradient, w_color_gold,
            w_image, w_image_blabar, w_slideshow, w_md,
            w_ics_list, w_ics_week, w_ics_month, w_ics_schedule,
            w_video_drone, w_video_murana, w_video_fagel, w_video_snow,
            w_video_drone_720, w_video_murana_720, w_video_fagel_720, w_video_snow_720,
            w_pdf_medlem,
            lbl_clock_td, lbl_clock_t, lbl_clock_12h, lbl_clock_day,
            lbl_text_n, lbl_text_s, lbl_text_i,
            lbl_color_sol, lbl_color_gr, lbl_color_gd,
            lbl_image, lbl_image_bb, lbl_slideshow, lbl_md,
            lbl_ics_list, lbl_ics_week, lbl_ics_month, lbl_ics_schedule,
            lbl_video_drone, lbl_video_murana, lbl_video_fagel, lbl_video_snow,
            lbl_video_drone_720, lbl_video_murana_720, lbl_video_fagel_720, lbl_video_snow_720,
            lbl_pdf_medlem,
        ]
        db.add_all(all_widgets)
        db.flush()

        # Konvertera PDF till bilder
        from app.routes.admin.media import (
            _convert_pdf_to_images, PDF_PAGES_DIR,
            _generate_video_thumbnail, VIDEO_THUMBS_DIR,
        )
        import os as _os
        _os.makedirs(PDF_PAGES_DIR, exist_ok=True)
        _os.makedirs(VIDEO_THUMBS_DIR, exist_ok=True)
        for uuid_name, orig_name in _SEED_PDFS:
            pdf_path = _os.path.join(_UPLOADS, uuid_name)
            if _os.path.exists(pdf_path):
                _convert_pdf_to_images(pdf_path, uuid_name[:-4])
        for uuid_name, orig_name in _SEED_VIDEOS:
            vid_path = _os.path.join(_UPLOADS, uuid_name)
            if _os.path.exists(vid_path):
                _generate_video_thumbnail(vid_path, uuid_name.rsplit(".", 1)[0])

        # ── IcsCache – förpopulera med dagens kalenderdata ────────────────────
        _ics_raw = generate_ics()
        for _w in [w_ics_list, w_ics_week, w_ics_month, w_ics_schedule]:
            db.add(IcsCache(widget_id=_w.id, source_url=DEV_CAL_URL, raw_ics=_ics_raw))
        db.flush()

        # ── Kanaler ───────────────────────────────────────────────────────────
        ch_clock = Channel(name="Klockor",     aspect_ratio="16:9")
        ch_media = Channel(name="Media",       aspect_ratio="16:9")
        ch_media_720 = Channel(name="Media 720p", aspect_ratio="16:9")
        ch_hwaccel = Channel(name="Hwaccel-test (1 video)", aspect_ratio="16:9")
        ch_kal   = Channel(name="Kalender",    aspect_ratio="16:9")
        ch_lay   = Channel(name="Layout-test", aspect_ratio="16:9")
        ch_port  = Channel(name="Porträtt",    aspect_ratio="9:16")
        db.add_all([ch_clock, ch_media, ch_media_720, ch_hwaccel, ch_kal, ch_lay, ch_port])
        db.flush()

        # ── Skärmar ───────────────────────────────────────────────────────────
        db.add_all([
            Screen(name="Klockor",     slug="klockor",      channel_id=ch_clock.id),
            Screen(name="Media",       slug="media",        channel_id=ch_media.id),
            Screen(name="Media 720p",  slug="media-720",    channel_id=ch_media_720.id),
            Screen(name="Hwaccel-test", slug="hwaccel",     channel_id=ch_hwaccel.id,
                   video_capability="single"),
            Screen(name="Kalender",    slug="kalender",     channel_id=ch_kal.id),
            Screen(name="Layout-test", slug="layout-test",  channel_id=ch_lay.id),
            Screen(name="Porträtt",    slug="portratt",     channel_id=ch_port.id),
        ])
        db.flush()

        # ── Layouter ─────────────────────────────────────────────────────────
        l_clock = Layout(name="Klockor – fullskärm",      aspect_ratio="16:9")
        l_media = Layout(name="Media – fullskärm",        aspect_ratio="16:9")
        l_kal   = Layout(name="Kalender – fullskärm",     aspect_ratio="16:9")
        l_split = Layout(name="Landskap 60/40",           aspect_ratio="16:9")
        l_full  = Layout(name="Landskap fullskärm",       aspect_ratio="16:9")
        l_bar   = Layout(name="Landskap huvud+sidfält",   aspect_ratio="16:9")
        l_port  = Layout(name="Porträtt – fullskärm",     aspect_ratio="9:16")
        db.add_all([l_clock, l_media, l_kal, l_split, l_full, l_bar, l_port])
        db.flush()

        # ── Zoner ─────────────────────────────────────────────────────────────
        z_clock = LayoutZone(
            layout_id=l_clock.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=5, transition="fade",
        )
        z_media = LayoutZone(
            layout_id=l_media.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=8, transition="fade",
        )
        z_kal = LayoutZone(
            layout_id=l_kal.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=8,
            transition="slide", transition_direction="left",
        )
        z_split_left = LayoutZone(
            layout_id=l_split.id, name="Vänster", role="schedulable",
            x_pct=0, y_pct=0, w_pct=60, h_pct=100, rotation_seconds=10,
            transition="slide", transition_direction="left",
        )
        z_split_right = LayoutZone(
            layout_id=l_split.id, name="Höger", role="schedulable",
            x_pct=60, y_pct=0, w_pct=40, h_pct=100, rotation_seconds=10, transition="fade",
        )
        z_full = LayoutZone(
            layout_id=l_full.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=8, transition="fade",
        )
        z_bar_main = LayoutZone(
            layout_id=l_bar.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=75, h_pct=100, rotation_seconds=8,
            transition="slide", transition_direction="up",
        )
        z_bar_side = LayoutZone(
            layout_id=l_bar.id, name="Sidfält", role="persistent",
            x_pct=75, y_pct=0, w_pct=25, h_pct=100,
        )
        z_port = LayoutZone(
            layout_id=l_port.id, name="Huvud", role="schedulable",
            x_pct=0, y_pct=0, w_pct=100, h_pct=100, rotation_seconds=8, transition="fade",
        )
        db.add_all([z_clock, z_media, z_kal, z_split_left, z_split_right,
                    z_full, z_bar_main, z_bar_side, z_port])
        db.flush()

        # ── Layout-tilldelningar ──────────────────────────────────────────────
        # Enkla kanaler: en layout var, ingen duration behövs
        db.add_all([
            ChannelLayoutAssignment(channel_id=ch_clock.id, layout_id=l_clock.id, priority=0),
            ChannelLayoutAssignment(channel_id=ch_media.id, layout_id=l_media.id, priority=0),
            ChannelLayoutAssignment(channel_id=ch_media_720.id, layout_id=l_media.id, priority=0),
            ChannelLayoutAssignment(channel_id=ch_hwaccel.id, layout_id=l_media.id, priority=0),
            ChannelLayoutAssignment(channel_id=ch_kal.id,   layout_id=l_kal.id,   priority=0),
            ChannelLayoutAssignment(channel_id=ch_port.id,  layout_id=l_port.id,  priority=0),
            # layout-test roterar mellan tre layouter
            # split: max(3×10, 3×10) = 30 s  |  full: 3×8 = 24 s  |  bar: 16+8 = 24 s
            ChannelLayoutAssignment(
                channel_id=ch_lay.id, layout_id=l_split.id, priority=0, duration_seconds=30,
                transition="slide", transition_direction="left",
            ),
            ChannelLayoutAssignment(
                channel_id=ch_lay.id, layout_id=l_full.id, priority=1, duration_seconds=24,
                transition="fade",
            ),
            ChannelLayoutAssignment(
                channel_id=ch_lay.id, layout_id=l_bar.id, priority=2, duration_seconds=24,
                transition="slide", transition_direction="right",
            ),
        ])
        db.flush()

        def wl1(w, lbl) -> dict:
            return {"widgets": _lbl_row(w, lbl)}

        # ── Vyer – klockor (5 s/vy) ───────────────────────────────────────────
        views_clock = [
            View(channel_id=ch_clock.id, zone_id=z_clock.id, position=0,
                 name="Tid + datum", enabled=True,
                 layout_json=wl1(w_clock_td, lbl_clock_td)),
            View(channel_id=ch_clock.id, zone_id=z_clock.id, position=1,
                 name="Enbart tid", enabled=True,
                 layout_json=wl1(w_clock_t, lbl_clock_t)),
            View(channel_id=ch_clock.id, zone_id=z_clock.id, position=2,
                 name="12h AM/PM", enabled=True,
                 layout_json=wl1(w_clock_12h, lbl_clock_12h)),
            View(channel_id=ch_clock.id, zone_id=z_clock.id, position=3,
                 name="Dag + datum (stor, gradient)", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_day.id,      "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_day.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]

        # ── Vyer – media ──────────────────────────────────────────────────────
        views_media = [
            View(channel_id=ch_media.id, zone_id=z_media.id, position=0,
                 name="Bild blåbär (cover)", enabled=True, duration_seconds=8,
                 layout_json=wl1(w_image_blabar, lbl_image_bb)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=1,
                 name="Bild tall (contain)", enabled=True, duration_seconds=8,
                 transition="fade",
                 layout_json=wl1(w_image, lbl_image)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=2,
                 name="Bildspel (3 bilder × 5 s)", enabled=True, duration_seconds=16,
                 transition="none",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=3,
                 name="Video drone", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_drone, lbl_video_drone)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=4,
                 name="Video murana", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_murana, lbl_video_murana)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=5,
                 name="Video fågel", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_fagel, lbl_video_fagel)),
            View(channel_id=ch_media.id, zone_id=z_media.id, position=6,
                 name="PDF Medlemsinfo", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_pdf_medlem, lbl_pdf_medlem)),
        ]

        # ── Vyer – media 720p ─────────────────────────────────────────────────
        views_media_720 = [
            View(channel_id=ch_media_720.id, zone_id=z_media.id, position=0,
                 name="Video drone 720p", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_drone_720, lbl_video_drone_720)),
            View(channel_id=ch_media_720.id, zone_id=z_media.id, position=1,
                 name="Video murana 720p", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_murana_720, lbl_video_murana_720)),
            View(channel_id=ch_media_720.id, zone_id=z_media.id, position=2,
                 name="Video fågel 720p", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_fagel_720, lbl_video_fagel_720)),
            View(channel_id=ch_media_720.id, zone_id=z_media.id, position=3,
                 name="Video snö 720p", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_snow_720, lbl_video_snow_720)),
        ]

        # ── Vyer – hwaccel-test (en enda video, 720p drone) ──────────────────
        views_hwaccel = [
            View(channel_id=ch_hwaccel.id, zone_id=z_media.id, position=0,
                 name="Video drone 720p (loop)", enabled=True, duration_seconds=None,
                 transition="none",
                 layout_json=wl1(w_video_drone_720, lbl_video_drone_720)),
        ]

        # ── Vyer – kalender (8–10 s/vy) ──────────────────────────────────────
        views_kal = [
            View(channel_id=ch_kal.id, zone_id=z_kal.id, position=0,
                 name="Lista", enabled=True, duration_seconds=8,
                 layout_json=wl1(w_ics_list, lbl_ics_list)),
            View(channel_id=ch_kal.id, zone_id=z_kal.id, position=1,
                 name="Vecka", enabled=True, duration_seconds=8,
                 layout_json=wl1(w_ics_week, lbl_ics_week)),
            View(channel_id=ch_kal.id, zone_id=z_kal.id, position=2,
                 name="Månad", enabled=True, duration_seconds=10,
                 layout_json=wl1(w_ics_month, lbl_ics_month)),
            View(channel_id=ch_kal.id, zone_id=z_kal.id, position=3,
                 name="Schema", enabled=True, duration_seconds=8,
                 layout_json=wl1(w_ics_schedule, lbl_ics_schedule)),
        ]

        # ── Vyer – layout-test: split vänster (10 s/vy) ──────────────────────
        views_split_left = [
            View(channel_id=ch_lay.id, zone_id=z_split_left.id, position=0,
                 name="Klocka tid+datum", enabled=True,
                 layout_json=wl1(w_clock_td, lbl_clock_td)),
            View(channel_id=ch_lay.id, zone_id=z_split_left.id, position=1,
                 name="Klocka enbart tid", enabled=True,
                 transition="slide", transition_direction="right",
                 layout_json=wl1(w_clock_t, lbl_clock_t)),
            View(channel_id=ch_lay.id, zone_id=z_split_left.id, position=2,
                 name="Markdown", enabled=True, transition="slide", transition_direction="up",
                 layout_json=wl1(w_md, lbl_md)),
        ]
        # ── Vyer – layout-test: split höger (10 s/vy) ────────────────────────
        views_split_right = [
            View(channel_id=ch_lay.id, zone_id=z_split_right.id, position=0,
                 name="Färgblock gradient", enabled=True,
                 layout_json=wl1(w_color_gradient, lbl_color_gr)),
            View(channel_id=ch_lay.id, zone_id=z_split_right.id, position=1,
                 name="Text versaler", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_styled.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_s.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_lay.id, zone_id=z_split_right.id, position=2,
                 name="Text kursiv", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gold.id,  "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_italic.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_i.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]
        # ── Vyer – layout-test: fullskärm (8 s/vy) ───────────────────────────
        views_full = [
            View(channel_id=ch_lay.id, zone_id=z_full.id, position=0,
                 name="Bild blåbär", enabled=True, duration_seconds=8,
                 layout_json=wl1(w_image_blabar, lbl_image_bb)),
            View(channel_id=ch_lay.id, zone_id=z_full.id, position=1,
                 name="Klocka dag (gradient)", enabled=True, duration_seconds=8,
                 transition="slide", transition_direction="up",
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_day.id,      "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_day.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_lay.id, zone_id=z_full.id, position=2,
                 name="Text normal", enabled=True, duration_seconds=8,
                 transition="none",
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_normal.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_n.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]
        # ── Vyer – layout-test: bar huvud + sidfält ───────────────────────────
        views_bar_main = [
            View(channel_id=ch_lay.id, zone_id=z_bar_main.id, position=0,
                 name="Bildspel", enabled=True, duration_seconds=16,
                 transition="none",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_lay.id, zone_id=z_bar_main.id, position=1,
                 name="Klocka (gradient)", enabled=True, duration_seconds=8,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_td.id,       "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_td.id,     "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
        ]
        views_bar_side = [
            View(channel_id=ch_lay.id, zone_id=z_bar_side.id, position=0,
                 name="Sidfält – klocka", enabled=True,
                 layout_json={"widgets": [
                     {"widget_id": w_color_solid.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_t.id,     "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                 ]}),
        ]

        # ── Vyer – porträtt ───────────────────────────────────────────────────
        views_port = [
            View(channel_id=ch_port.id, zone_id=z_port.id, position=0,
                 name="Klocka (gradient)", enabled=True, duration_seconds=8,
                 layout_json={"widgets": [
                     {"widget_id": w_color_gradient.id, "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_clock_td.id,       "x": 0, "y": 2, "w": 12, "h": 5, "z_index": 1},
                     {"widget_id": lbl_clock_td.id,     "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=1,
                 name="Bild tall (contain)", enabled=True, duration_seconds=8,
                 transition="fade",
                 layout_json=wl1(w_image, lbl_image)),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=2,
                 name="Bildspel", enabled=True, duration_seconds=16,
                 transition="slide", transition_direction="up",
                 layout_json=wl1(w_slideshow, lbl_slideshow)),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=3,
                 name="Text versaler (guld)", enabled=True, duration_seconds=8,
                 transition="slide", transition_direction="left",
                 layout_json={"widgets": [
                     {"widget_id": w_color_gold.id,  "x": 0, "y": 0, "w": 12, "h": 9, "z_index": 0},
                     {"widget_id": w_text_styled.id, "x": 0, "y": 3, "w": 12, "h": 3, "z_index": 1},
                     {"widget_id": lbl_text_s.id,    "x": 0, "y": 8, "w": 12, "h": 1, "z_index": 10},
                 ]}),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=4,
                 name="Markdown", enabled=True, duration_seconds=8,
                 transition="none",
                 layout_json=wl1(w_md, lbl_md)),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=5,
                 name="Kalender schema", enabled=True, duration_seconds=8,
                 transition="fade",
                 layout_json=wl1(w_ics_schedule, lbl_ics_schedule)),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=6,
                 name="Kalender lista", enabled=True, duration_seconds=8,
                 transition="slide", transition_direction="up",
                 layout_json=wl1(w_ics_list, lbl_ics_list)),
            View(channel_id=ch_port.id, zone_id=z_port.id, position=7,
                 name="Video snö (porträtt)", enabled=True, duration_seconds=20,
                 transition="fade",
                 layout_json=wl1(w_video_snow, lbl_video_snow)),
        ]

        all_views = (views_clock + views_media + views_media_720 + views_hwaccel + views_kal
                     + views_split_left + views_split_right + views_full
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

        # ── Inställningar ────────────────────────────────────────────────────
        from app.config import DEFAULT_TIMEZONE
        db.add(AppSetting(key="timezone", value=DEFAULT_TIMEZONE))

        db.commit()

    views_n = len(all_views)
    log.warning(
        "DEV_SEED klar: 7 kanaler (/s/klockor, /s/media, /s/media-720, /s/hwaccel, "
        "/s/kalender, /s/layout-test, /s/portratt), "
        "%d widgets, %d vyer, 8 mediafiler, ICS-kalender på /dev-cal.ics",
        len(all_widgets), views_n,
    )
