# Roadmap – svk-dash

## Klart

### Kärnsystem
- Skärmar, vyer och widget-bibliotek (CRUD)
- Grid-baserad layout-editor med drag, resize, z-index och opacity
- Inline-widgets (klocka, text, färgblock, bild, bildspel) direkt i vylayouten
- Kiosk-läge med SSE-driven rotation och widget-uppdatering i realtid
- Delegerad redigering via hemlig token-URL
- Formulärbaserade config-editorer för alla widget-typer
- Multi-source ICS: flera URL:er per kalender-widget
- Revisionshistorik för widgets (max 20, med återställning i modal)
- Föregående/nästa-navigering mellan vyer i admin-editorn
- Hover-overlay med pil-navigation och paus i kiosk-läge
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
- `slideshow`-widget: roterande bilder med fade/slide-övergång, konfigurerbart intervall
- Båda tillgängliga som bibliotekswidgets och som inline-widgets i layouteditorn

### Mediebibliotek
- Administrationssida `/admin/media` med grid- och listvy, mappstruktur
- Batch-markering med flytta/ta bort
- Visar hur många widgets som använder varje bild
- Radera bild med varning om den är i bruk
- Bildväljare (modal) med mappnavigering i widget_detail och view_detail
- Uppladdade filer registreras i DB (`MediaFile`) med originalnamn

---

## Planerat

### Layout-system med zoner  *(stor feature, tre steg)*

En skärm delas upp i namngivna zoner via ett återanvändbart layout-template. Möjliggör t.ex. en stående 9:16-skärm med en stor toppzon, två A-format-zoner i mitten och en persistent remsa längst ned med logga och klocka.

**Zoner har två roller:**
- `persistent` — alltid synlig, innehåller widgets direkt (logga, klocka)
- `schedulable` — roterar mellan vyer enligt schema (kalender, info)

**Arv:** layout-template definierar default-innehåll för persistenta zoner. Varje skärm kan välja att använda template-default eller sätta en egen override (allt-eller-inget per zon).

**Layout-växling:** en skärm kan schemalägga byte mellan layouter (t.ex. 3-zon dagtid → helskärm kvällstid) baserat på veckodagar och tidsintervall.

Steg:
1. **Layouts + zon-editor** — DB-modeller, `/admin/layouts`, visuell drag/resize-editor
2. **Koppla skärmar** — `ScreenLayoutAssignment`, `ScreenZoneOverride`, automatisk migration av befintliga vyer
3. **Schemaläggning** — vy-rotation inom zoner, layout-växling per schema

Se CLAUDE.md → *Planerad arkitektur: Layout-system* för fullständig datamodell.

### Kiosk-bootstrap för Raspberry Pi
Setup-skript som konfigurerar RPi i kiosk-läge: Chromium helskärm, autostart, roterande skärm, nätverkskonfiguration.
