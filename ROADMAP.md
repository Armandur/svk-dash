# Roadmap – svk-dash

## Klart

### Kärnsystem
- Skärmar, vyer och widget-bibliotek (CRUD)
- Grid-baserad layout-editor med drag, resize, z-index och opacity
- Inline-widgets (klocka, text, färgblock, bild, bildspel) direkt i vylayouten
- Kiosk-läge med SSE-driven widget-uppdatering i realtid
- Delegerad redigering via hemlig token-URL
- Formulärbaserade config-editorer för alla widget-typer
- Multi-source ICS: flera URL:er per kalender-widget
- Revisionshistorik för widgets (max 20, med återställning i modal)
- Föregående/nästa-navigering mellan vyer i admin-editorn
- Anpassad CSS-editor per widget
- Förbättrad color picker (swatch + hex-fält, synkade)
- Widget-bibliotekssida med kategori-sidopanel
- Widget-picker-modal i layouteditorn (kategori-sidopanel + bibliotek/inline)

### ICS-kalenderwidgetar
- `ics_list`: händelselista med dag-gruppering, auto-scroll, scrollbar
- `ics_month`: månadskalender med flerdagshändelser som balkspann
- `ics_week`: veckovy i kolumnformat (mån–sön eller sön–lör)
- `ics_schedule`: blockschema med tidsaxel, parallella händelser, nu-linje
- Färgkodning per ICS-källa
- Prefix- och nyckelordsfiltrering
- Outlook-status: FREE (frånvaro), TENTATIVE, PRIVATE
- Online-mötesmärke (Teams/Zoom/Meet etc.), konfigurerbart per widget
- Visa plats, max per dag, konfigurerbart antal dagar framåt
- ICS-hämtning deduplicerad (en request per URL även om flera widgets delar källa)

### Bild- och bildspelswidgetar
- `image`-widget: enstaka bild, extern URL eller filuppladdning, konfigurerbar passning (cover/contain/fill)
- `slideshow`-widget: roterande bilder med fade/slide/wipe/zoom-övergång, konfigurerbart intervall
- Båda tillgängliga som bibliotekswidgets och som inline-widgets i layouteditorn
- Originalfilnamn visas i editorn när bild väljs från bibliotek eller laddas upp

### Layout-system med zoner *(steg 1–3, komplett)*
- DB-modeller: `Layout`, `LayoutZone`, `ScreenLayoutAssignment`
- Admin-UI: `/admin/layouts` — skapa/redigera layouts med visuell zon-editor (drag/resize)
- Koppla skärmar till layouts via `ScreenLayoutAssignment`
- Persistenta zoner med direktwidgets (logga, klocka) och schemalagda zoner som roterar vyer
- Kiosk-läge hanterar multi-zon-rendering med oberoende vy-rotation per zon
- Per-zon-inställningar i admin: standardtid, övergångstyp (fade/slide/ingen), riktning
- Debug-overlay (hover-aktiverad) med skärmnamn, lokal IP, SSE-ålder och reconnect-räknare

### Schemaläggning och layout-rotation
- `schedule_json` på både `ScreenLayoutAssignment` och `View`: stöder typerna `always`, `weekly`, `monthly`, `yearly`, `dates` samt valfritt tidsintervall (time_start/time_end)
- Schema-modal i admin med checkboxar för veckodagar, dag-i-månaden, specifika datum m.m.
- Layout-rotation: `duration_seconds` per tilldelning styr hur länge en layout visas
- Alla aktiva layouter förrenderas i DOM vid sidladdning — rotation sker sömlöst på klientsidan utan `location.reload()`
- Övergångstyp (fade/slide/none) och längd (ms) konfigurerbart per layout-tilldelning
- Vy-rotation inom zoner: slide-övergång scoped till zon-elementet, fade via CSS opacity-transition
- Legacy-vy-rotation (skärmar utan layout) borttagen

### Kvalitet och robusthet
- Widget-renderingsfel ger placeholder istället för 500-svar
- JSON-validering av inkommande layout-data med svenska felmeddelanden
- SQL-filtrering i broadcast och medieradering (tidigare laddades allt i minnet)
- Zombie-timers i kiosk: klocka och auto-scroll pausas vid paus-läge
- Mediepicker lazy-initierad (DOM-ordningsbug fixad)
- Reaktiv UI: namn, bildval och token uppdateras direkt utan omladdning

### Mediebibliotek
- Administrationssida `/admin/media` med grid- och listvy, mappstruktur
- Batch-markering med flytta/ta bort
- Visar hur många widgets som använder varje bild
- Radera bild med varning om den är i bruk
- Bildväljare (modal) med mappnavigering i widget_detail och view_detail
- Uppladdade filer registreras i DB (`MediaFile`) med originalnamn

---

## Planerat

### Kiosk-bootstrap för Raspberry Pi
Setup-skript som konfigurerar RPi i kiosk-läge: Chromium helskärm, autostart, roterande skärm, NTP-väntan, nätverkskonfiguration. Läggs i `deploy/kiosk-setup/`.

### Observabilitet och larm
- Live-status på admin-dashboard: grön/gul/röd indikator baserad på heartbeat-ålder
- Larm vid död skärm: notis via konfigurerbar kanal (SMTP, webhook) när heartbeat > 15 min
- `alert_sent_at` på `Screen` för att förhindra larm-spam

### Skärm-hårdvarukontroll
- HDMI-CEC via SSE-event (`display_power`) — stäng av skärmen nattetid
- Schema per skärm för tändning/släckning
