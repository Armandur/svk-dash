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

### Bild- och bildspelswidgetar
- `image`-widget: enstaka bild, extern URL eller filuppladdning, konfigurerbar passning (cover/contain/fill)
- `slideshow`-widget: roterande bilder med fade-övergång, konfigurerbart intervall
- Båda tillgängliga som bibliotekswidgets och som inline-widgets i layouteditorn
- Inline-bildspel har per-instans bildlista med URL-tillägg och filuppladdning

### Widget-picker: gemensam modal för bibliotek och inline
Ersätter de separata "Lägg till widget"- och "Lägg till inline-widget"-formulären i layouteditorn med en enda **"+ Lägg till widget"**-knapp som öppnar en modal.

Modalen har två flikar:

**Bibliotek** — välj en befintlig widget. Widgets visas grupperade efter kategori (Kalender, Media, Innehåll, Övrigt). Klicka på en grupp för att expandera och se tillgängliga widgets som klickbara kort (namn + kind-badge). Klicka ett kort → läggs till i layouten.

**Inline** — kompakt kortgrid med inline-typerna (klocka, text, färgblock, bild, bildspel). Ett klick lägger till direkt.

Samma grupperingstänk appliceras på `/admin/widgets`: listan grupperas per kategori med expanderbara sektioner eller filterbara flikar. "Ny widget"-knappen öppnar en modal där man väljer typ (grupperad) innan man fyller i namn.

### Mediebibliotek
Centralt hantering av uppladdade bildfiler.

- Administrationssida `/admin/media` med thumbnailgrid, filnamn, storlek och uppladdningsdatum
- Visar hur många widgets som använder varje bild (scanning av `config_json` och `layout_json`)
- Radera bild med varning om den är i bruk
- Ersätt bild in-place: ladda upp ny fil till samma UUID-sökväg → alla widgets uppdateras automatiskt utan konfigurationsändringar
- DB-tabell `UploadedFile` (`filename`, `original_name`, `size`, `created_at`) för att bevara originalfilnamn — befintliga uploads backfylls med UUID som fallback
- Bildväljare (modal): "Välj från bibliotek"-knapp bredvid URL-fält och uppladdningsknappar i widget_detail.html och view_detail.html

### Schema-baserad vy-rotation
Visa specifika vyer vid specifika tider/dagar (t.ex. "välkomstvy 08–09 på vardagar"). Modellen `ViewSchedule` finns redan i databasen — logik och admin-UI saknas.

### Kiosk-bootstrap för Raspberry Pi
Setup-skript som konfigurerar RPi i kiosk-läge: Chromium helskärm, autostart, roterande skärm, nätverkskonfiguration.
