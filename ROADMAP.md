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

### Spelartelemetri – rapportering från kiosk till admin

Varje ansluten kiosk-klient rapporterar periodiskt diagnostikdata till servern via ett dedikerat POST-anrop. Servern lagrar informationen per skärm och visar den i admin-gränssnittet.

**Vad klienten rapporterar:**
- Nätverks-IP som servern ser på anropet (= LAN-IP om de är på samma nät, annars publik IP)
- Skärmupplösning (`screen.width × screen.height`) och fönsterstorlek (`window.innerWidth × innerHeight`)
- User agent (identifierar browser och OS, t.ex. `Chromium/124 Linux armv7l`)
- Kiosk-JS-version (konstant i kiosk.js, t.ex. `dev` eller git-SHA vid byggd release)
- Tid sedan sidan laddades (uptime i sekunder — indikerar t.ex. om skärmen startat om)
- Aktivt layout-ID och vy-position per zon (vad som visas just nu)
- SSE-reconnect-räknare (indikerar instabilt nätverk)

**Teknisk plan:**
1. Nytt endpoint `POST /s/<slug>/telemetry` — autentiseras med samma slug, inget lösenord krävs (icke-känslig driftsinfo). Rate-limitad till max 1 req/min per skärm.
2. Nya kolumner på `Screen`: `client_ip`, `client_user_agent`, `client_resolution`, `client_uptime_seconds`, `client_js_version`, `client_reconnects`, `telemetry_at` (tidsstämpel).
3. `kiosk.js` skickar telemetri vid sidladdning och sedan var 5:e minut (inbyggt i det befintliga heartbeat-intervallet).
4. Admin-skärmsidan (`screen_detail.html`) visar en "Diagnostik"-panel med senast rapporterad data och ålder på rapporten.
5. Admin-dashboard visar en kompakt statusindikator per skärm (grön/gul/röd baserat på `telemetry_at`-ålder, klickbar för detaljer).

**Avgränsningar:**
- Ingen historik sparas — bara senaste rapport per skärm.
- Batteristatus (Battery API) utelämnas — inte relevant för Pi.
- Ingen GPS eller annan känslig data.

### Skärm-hårdvarukontroll
- HDMI-CEC via SSE-event (`display_power`) — stäng av skärmen nattetid
- Schema per skärm för tändning/släckning
