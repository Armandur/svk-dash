# Roadmap – svk-dash

## Klart

- Skärmar, vyer och widget-bibliotek (CRUD)
- Grid-baserad layout-editor med drag, resize, z-index och opacity
- Inline-widgets (klocka, text, färgblock) direkt i vylayouten
- Kiosk-läge med SSE-driven rotation och widget-uppdatering i realtid
- Delegerad redigering via hemlig token-URL
- Formulärbaserade config-editorer för alla widget-typer (ersätter rå JSON)
- Multi-source ICS: flera URL:er per kalender-widget (composite PK-migration)
- Revisionshistorik för widgets (max 20, med återställning)
- Föregående/nästa-navigering mellan vyer i admin-editorn
- Hover-overlay med pil-navigation och paus i kiosk-läge
- `ics_list`: händelselista med dag-gruppering
- `ics_month`: månadskalender med dagens datum markerat

---

## Planerat

### ICS-kalender – förbättringar (gemensamma)

| # | Funktion | Widget |
|---|----------|--------|
| 1 | Visa start- och/eller sluttid (konfigurerbart: av / bara start / start+slut) | list, week |
| 2 | Flerdagshändelser visas som spann i månadsvy | month |
| 3 | Heldagshändelser separerade överst per dag | list |
| 4 | Konfigurerbart antal dagar framåt i listvy (default 30) | list |
| 5 | Färgkodning per ICS-källa (en färg i vänsterkanten per URL) | list, week |
| 6 | Filtrera bort händelser via nyckelord eller prefix (t.ex. `!A - `) | list, month, week |
| 7 | Visa plats (`LOCATION`) under händelsenamnet (av/på) | list, week |
| 8 | Max antal händelser per dag med "+N till"-trunkering | list |

### `ics_week` – ny widget-typ

Veckovy i tabellformat (mån–sön eller sön–lör).

- `week_offset`: 0 = denna vecka, 1 = nästa vecka, -1 = förra veckan osv.
- Heldagshändelser i separat rad överst
- Tidsaxel (konfigurerbart från/till-timme)
- Ärver färgkodning och prefix-filtrering från gemensam logik

### Övrigt

- Bildspels-widget: auto-rotera bilder från uppladdad mapp
- Schema-baserad vy-rotation (specifika vyer vid specifika tider/dagar)
- Kiosk-bootstrap-skript för Raspberry Pi

---

## Beslutade designval

- `get_ics_urls(config)` normaliserar str/list/dict → `list[str]` i `ics_fetcher.py`
- Prefix-/nyckelordsfilter implementeras i en delad hjälpfunktion i `ics_fetcher.py` eller nytt `app/widgets/ics_common.py`
- Färgkodning: lista med förutbestämda CSS-färger indexerade på URL:ens position i listan
- `ics_week` registreras som ny kind i `WIDGET_KINDS` och får egen renderer `app/widgets/ics_week.py`
