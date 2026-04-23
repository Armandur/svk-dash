# Roadmap – svk-dash

## Klart

### Kärnsystem
- Skärmar, vyer och widget-bibliotek (CRUD)
- Grid-baserad layout-editor med drag, resize, z-index och opacity
- Inline-widgets (klocka, text, färgblock) direkt i vylayouten
- Kiosk-läge med SSE-driven rotation och widget-uppdatering i realtid
- Delegerad redigering via hemlig token-URL
- Formulärbaserade config-editorer för alla widget-typer
- Multi-source ICS: flera URL:er per kalender-widget
- Revisionshistorik för widgets (max 20, med återställning)
- Föregående/nästa-navigering mellan vyer i admin-editorn
- Hover-overlay med pil-navigation och paus i kiosk-läge
- Anpassad CSS-editor per widget
- Förbättrad color picker (swatch + hex-fält, synkade)

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

---

## Planerat

### Bildspels-widget
Auto-rotera bilder från en uppladdad mapp. Kräver filuppladdning i admin och en renderer med konfigurerbart intervall.

### Schema-baserad vy-rotation
Visa specifika vyer vid specifika tider/dagar (t.ex. "välkomstvy 08–09 på vardagar"). Modellen `ViewSchedule` finns redan i databasen — logik och admin-UI saknas.

### Kiosk-bootstrap för Raspberry Pi
Setup-skript som konfigurerar RPi i kiosk-läge: Chromium helskärm, autostart, roterande skärm, nätverkskonfiguration.
