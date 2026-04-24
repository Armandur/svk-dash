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
- Widget-bibliotekssida med kategori-sidopanel
- Widget-picker-modal i layouteditorn (kategori-sidopanel + bibliotek/inline)
- Varumärkespalett (`BrandColor`, `/admin/palette`): lägg till, döp om, ta bort, byt ordning
- Pickr-baserad färgväljare med opacitetsstöd i widget- och vyeditorn (ersätter OS-inbyggd `<input type="color">`)
- Live klientmetadata per skärm: IP, webbläsare/OS, upplösning, tidszon — realtids-polling med Page Visibility API
- Cache-busting för kiosk.js via fil-mtime (`?v=...`)

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
- Per-widget-tidszon, visa/dölj klocktider, anpassad text vid inga händelser

### Bild- och bildspelswidgetar
- `image`-widget: enstaka bild, extern URL eller filuppladdning, konfigurerbar passning (cover/contain/fill), hörnradius, bildposition (object-position)
- `slideshow`-widget: roterande bilder med fade/slide/wipe/zoom-övergång, konfigurerbart intervall, bildtexter (caption) per bild med halvtransparent overlay
- Båda tillgängliga som bibliotekswidgets och som inline-widgets i layouteditorn
- Originalfilnamn visas i editorn när bild väljs från bibliotek eller laddas upp

### Klocka/datum-widget
- Format: tid+datum, enbart tid, enbart datum, dag+tid
- Tidszon och locale per widget
- Visa/dölj sekunder
- 12- eller 24-timmarsformat (AM/PM)
- Anpassat datumformat med strftime-koder (`%-d %B %Y` o.s.v.) och inbyggd hjälpruta med exempelkoder

### Text- och stilwidgetar
- Textwidget: fetstil, kursiv, versaler, bokstavsavstånd (`letter-spacing`)
- Färgblock: solid färg eller gradient (start-/slutfärg + vinkel), konfigurerbar hörnradius
- Gemensamma stilfält (text_color, bg_color, font_size, text_align, padding, italic, uppercase, letter_spacing) via `build_common_style()`

### Layout-system med zoner *(steg 1–3, komplett)*
- DB-modeller: `Layout`, `LayoutZone`, `ChannelLayoutAssignment`
- Admin-UI: `/admin/layouts` — skapa/redigera layouts med visuell zon-editor (drag/resize)
- Koppla kanaler till layouts via `ChannelLayoutAssignment`
- Persistenta zoner med direktwidgets (logga, klocka) och schemalagda zoner som roterar vyer
- Kiosk-läge hanterar multi-zon-rendering med oberoende vy-rotation per zon
- Per-zon-inställningar i admin: standardtid, övergångstyp (fade/slide/ingen), riktning
- Debug-overlay (hover-aktiverad) med skärmnamn, lokal IP, SSE-ålder och reconnect-räknare

### Kanal/skärm-separation
- Ny modell `Channel`: logisk konfiguration (layouter, zoner, vyer) frikopplad från fysisk enhet
- `Screen` pekar på en kanal via `channel_id`; byta kanal kräver ingen omkonfigurering av hårdvaran
- Virtuella kanaler: förbered innehåll innan hårdvaran är på plats (kanal utan kopplade skärmar)
- Admin `/admin/channels/`: lista, skapa, redigera kanaler; layout-/zon-/vy-hantering per kanal
- Admin `/admin/screens/`: bantad till hårdvaruinställningar + kanal-väljare + diagnostik
- Batchåtgärd: tilldela samma kanal till flera skärmar på en gång (t.ex. krisinfo)
- SSE-broadcast vid schema-/aktiveringsändring skickas till alla skärmar som delar kanalen

### Schemaläggning och layout-rotation
- `schedule_json` på både `ChannelLayoutAssignment` och `View`: stöder typerna `always`, `weekly`, `monthly`, `yearly`, `dates` samt valfritt tidsintervall (time_start/time_end)
- Schema-modal i admin med checkboxar för veckodagar, dag-i-månaden, specifika datum m.m.
- Layout-rotation: `duration_seconds` per tilldelning styr hur länge en layout visas
- Alla aktiva layouter förrenderas i DOM vid sidladdning — rotation sker sömlöst på klientsidan utan `location.reload()`
- Övergångstyp (fade/slide/none) och längd (ms) konfigurerbart per layout-tilldelning
- Vy-rotation inom zoner: slide-övergång scoped till zon-elementet, fade via CSS opacity-transition

### Kvalitet och robusthet
- Widget-renderingsfel ger placeholder istället för 500-svar
- JSON-validering av inkommande layout-data med svenska felmeddelanden
- SQL-filtrering i broadcast och medieradering
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
- Stöd för PDF (server-side renderad som bildsekvens) och video (mp4)
- Auto-genererade video-thumbnails och PDF-sidor

### Video- och PDF-widgetar
- `video`-widget: mp4-uppspelning med cover/contain-passning, loop, muted; kiosk-gren använder `data-src`/`preload=none` för att undvika parallell GPU-dekodning
- `pdf`-widget: server-side konvertering till bilder, page flipping i kiosk

### Kiosk-bootstrap för Raspberry Pi
- `deploy/kiosk-setup/install.sh` — idempotent setup-skript (NTP-väntan, autologin via getty, Chromium kiosk-flaggor, Caddy-reverse-proxy-stöd, managed policy mot Translate)
- `deploy/kiosk-setup/README.md` — RPi 3B + DSI Touch Display
- `deploy/kiosk-setup/README-rpi4.md` — RPi 4B + HDMI med dokumenterade begränsningar för hårdvarudekod av video

---

## Planerat

### Observabilitet och larm
- Live-status på admin-dashboard: grön/gul/röd indikator baserad på heartbeat-ålder
- Larm vid död skärm: notis via konfigurerbar kanal (SMTP, webhook) när heartbeat > 15 min
- `alert_sent_at` på `Screen` för att förhindra larm-spam

### Skärm-hårdvarukontroll
- HDMI-CEC via SSE-event (`display_power`) — stäng av skärmen nattetid
- Schema per skärm för tändning/släckning
