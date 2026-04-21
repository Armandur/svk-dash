# Skärmar – planeringsdokument

Internt verktyg för Svenska kyrkan för att driva informationsskärmar (dakboard-ersättare).
Arbetsnamn: **skarmar** (slutgiltigt namn/domän bestäms senare, t.ex. `skarmar.svky.se`).

---

## 1. Syfte och scope

Ersätt dakboard för interna skärmar inom Svenska kyrkan. Kärnbehovet är:

- Skapa namngivna **skärmar** (en skärm = en URL som körs i kiosk-läge på en Raspberry Pi eller liknande enhet).
- Varje skärm roterar mellan en eller flera **vyer**, där varje vy består av en eller flera **widgets**.
- Delegerad redigering av enskilda widgets via **hemlig token-URL** (samma modell som dakboards edit-URL), utan att kräva riktiga användarkonton i första versionen.

Kända produktionsanvändningsfall från start:

1. **Nya kyrkogårdens vaktmästeri** — skärm som pendlar mellan ICS-kalender (bokningar i kapellet och domkyrkan) och infosida från kyrkogårdschefen.
2. **Domprostens digitala namnskylt** — RPi med touchscreen som visar domprostens kalender i listform.

Scope för v1: intern drift, ingen publik åtkomst, svenska som enda språk, ingen multi-tenant-hantering.

---

## 2. Centrala begrepp

**Skärm (Screen)** — en fysisk display som pekar på en URL. Identifieras av en slug, t.ex. `vaktmasteriet-nya-kyrkogarden`. Kioskvyn nås på `/s/<slug>`.

**Vy (View)** — en layout som kan visas på skärmen. En skärm har 1..N vyer som roterar med konfigurerbar tid per vy. Varje vy har en grid-layout där widgets placeras.

**Widget** — en enskild komponent (ICS-kalender, markdown-text, bildspel, iframe, klocka). Widgets är fristående entiteter som kan återanvändas i flera vyer/skärmar. Varje widget har en **edit-token** som ger åtkomst till redigeringsvyn utan inloggning.

**Admin** — superanvändare (du) som hanterar skärmar, vyer och widget-layout. Loggar in med lösenord.

---

## 3. Teknisk stack

Samma grundval som kortlink-projektet för att hålla drift och mental overhead nere:

- **Backend**: FastAPI (Python 3.12+)
- **Templating**: Jinja2 (server-side rendering för både admin och kioskvy)
- **Databas**: SQLite med WAL-läge (enkel backup, ingen extern DB-server)
- **ORM**: SQLModel (SQLAlchemy + Pydantic i ett)
- **ICS-parsing**: `icalendar` + `recurring-ical-events` (sistnämnda hanterar RRULE-expansion)
- **HTTP-klient**: `httpx` (för att hämta ICS-URL:er server-side)
- **Bakgrundsjobb**: enkel `asyncio.create_task`-loop med `while True: await asyncio.sleep(...)` och obligatorisk `try/except Exception`-wrapper så att ett enskilt fel (t.ex. timeout på en ICS-URL) inte dödar hela loopen. APScheduler vore overkill för det här scopet.
- **HTML-sanitering**: `nh3` (Rust-baserad, modern ersättare till `bleach` som numera är opatchat)
- **Admin-frontend**: Jinja + HTMX + Tailwind via CDN — HTMX passar admin-CRUD:en bra.
- **Kiosk-frontend**: minimalt vanilla JS (ingen HTMX, ingen Tailwind, ingen Alpine). Total kontroll över DOM-uppdateringar är viktigt för långtidskörning utan minnesläckor.
- **Realtidspush till skärmar**: Server-Sent Events (SSE) via `sse-starlette` — enkelriktat server→klient, en öppen HTTP-connection per skärm.
- **Reverse proxy**: Caddy (automatisk HTTPS, samma som kortlinken)
- **Containerisering**: Docker + docker-compose

Ingen Node/npm-pipeline, inget SPA-ramverk — det skulle vara overkill och försvåra deploy.

---

## 4. Datamodell

```python
# Förenklad skiss

class Screen(SQLModel):
    id: int
    slug: str                    # unikt, används i URL (/s/<slug>)
    name: str                    # visningsnamn
    rotation_seconds: int = 30   # standard tid per vy
    performance_mode: str = "normal"  # "normal" i v1. "light" reserverat för
                                 # framtida MPA-variant om Pi Zero W kräver det.
    # Heartbeat-fält (uppdateras av SSE-hanteraren)
    last_seen_at: datetime | None
    last_connection_count: int = 0
    alert_sent_at: datetime | None  # undvik larm-spam
    created_at: datetime
    updated_at: datetime

class View(SQLModel):
    id: int
    screen_id: int               # FK → Screen
    position: int                # ordning i rotationen
    name: str
    duration_seconds: int | None # override av screen.rotation_seconds
    layout_json: dict            # grid-layout + vilka widgets som ligger var

class Widget(SQLModel):
    id: int
    kind: str                    # "ics_list" | "ics_month" | "markdown" |
                                 # "slideshow" | "iframe" | "clock" |
                                 # "raw_html" | "debug"
    name: str                    # intern identifierare för admin
    config_json: dict            # widget-specifik konfig
    edit_token: str              # slumpad, lång sträng (secrets.token_urlsafe(32))
    created_at: datetime
    updated_at: datetime

class IcsCache(SQLModel):
    widget_id: int               # FK → Widget (för ICS-widgets)
    raw_ics: str                 # senast hämtade ICS-innehåll
    fetched_at: datetime
    etag: str | None
    last_error: str | None

class WidgetRevision(SQLModel):
    id: int
    widget_id: int               # FK → Widget
    config_json: dict            # hela snapshoten vid spartillfället
    name_at_save: str
    saved_at: datetime
    saved_via: str               # "admin" | "edit_token"
    editor_ip: str | None        # sparas kort, diskret audit
    editor_user_agent: str | None
    # Rensningspolicy: max 20 revisioner per widget. Äldsta rensas
    # automatiskt vid varje ny spara.

class ViewSchedule(SQLModel):
    """Frivillig schemaläggning per vy. Om en vy har aktiva scheman
    visas den bara när minst ett schema matchar. Vyer utan scheman
    visas alltid (default)."""
    id: int
    view_id: int                 # FK → View
    cron_expression: str         # t.ex. "0 0 23 12 *" för "från 23 dec"
    duration_hours: int          # hur länge fönstret är öppet
    name: str                    # "Jul", "Påsk", etc.
    enabled: bool = True
```

**In-memory-state (inte i DB):**

```python
# SSE-anslutningsregister, lever i processminnet
# Mappar screen_id → set av asyncio.Queue för varje aktiv connection
# Varje queue har maxsize=10 — om en klient inte konsumerar i takt
# (t.ex. halvt tappad TCP-anslutning) droppas connectionen istället
# för att köa upp och orsaka minnesläckor.
active_connections: dict[int, set[asyncio.Queue]]
```

När admin trycker "reload" på en skärm läggs ett event i alla queues för den skärmen med `put_nowait`. Om det kastar `QueueFull` stängs connectionen och städas bort — klienten får återansluta via `EventSource`-auto-reconnect.

Eftersom detta bara är en process (ingen horisontell skalning) behövs ingen Redis/pub-sub. Om det någonsin skulle bli aktuellt att köra flera processer är det en enkel refaktor.

**Referensintegritet för widgets i `layout_json`:**

Eftersom `layout_json` refererar till widget-IDs utan formell FK behöver applikationslogiken säkerställa konsistens:

- Vid `DELETE /admin/widgets/<id>`: kontrollera alla `View.layout_json` i DB. Om widgeten används någonstans, returnera HTTP 409 Conflict med lista över berörda vyer. Admin måste ta bort widgeten ur vyerna först, eller explicit bekräfta med `?force=1` som rensar referenserna automatiskt.
- Vid render av en vy: om en widget-ID i `layout_json` inte längre finns, rendera en "Widget saknas"-placeholder istället för att krascha.

**Designval att notera:**

- `layout_json` på `View` istället för en separat `WidgetPlacement`-tabell. Layouten är alltid läst/skriven som helhet i admin, så JSON är enklare och SQLite hanterar det utmärkt.
- `config_json` på `Widget` istället för specialiserade tabeller per widget-typ. Validering sker i Pydantic-modeller i koden (en per `kind`), inte i schemat.
- ICS-cache är en separat tabell så att widget-konfig kan uppdateras utan att förlora senast hämtad data, och så att vi kan ha TTL-logik per widget.

---

## 5. Widget-typer (v1)

Alla widgets har gemensamt: `name`, `edit_token`, och konfig som definierar utseende/beteende.

### 5.1 `ics_list` — ICS-kalender i listform

Renderar kommande händelser som en kronologisk lista. Primärt use case för både vaktmästeri-skärmen och domprostens namnskylt.

```json
{
  "ics_url": "https://…/kalender.ics",
  "days_ahead": 14,
  "max_events": 20,
  "show_location": true,
  "show_description": false,
  "group_by_day": true,
  "calendar_label": "Domkyrkan"
}
```

- Server-side fetch med etag/if-modified-since. Cache-refresh var 10:e minut (konfigurerbart).
- RRULE expanderas via `recurring-ical-events`.
- Flera ICS-källor i samma lista stöds genom att tillåta `ics_url` som en array av `{url, label}`-objekt och färgkoda per källa.

### 5.2 `ics_month` — ICS-kalender i månadsvy

Traditionell rutnätskalender. Renderas server-side till HTML för att slippa tung JS.

```json
{
  "ics_url": "…",
  "weeks_to_show": 6,
  "start_on_monday": true,
  "highlight_today": true
}
```

### 5.3 `markdown` — Markdown/rik text-info

Kyrkogårdschefens use case. Redigeras via edit-token-URL med en enkel textarea + preview.

```json
{
  "content_md": "## Viktig information\n\n- Punkt ett\n- Punkt två",
  "font_size": "large",      // small | normal | large | huge
  "alignment": "left"
}
```

Markdown renderas med `markdown-it-py` och sanitiseras med `nh3` (Rust-baserad, modern ersättare till `bleach`). Även om tjänsten är intern är HTML-sanitisering god vana.

### 5.4 `slideshow` — Bild/bildspel

```json
{
  "images": [
    {"filename": "uploads/abc123.jpg", "caption": "…", "duration": 8},
    {"filename": "uploads/def456.jpg"}
  ],
  "transition": "fade",      // fade | none
  "object_fit": "cover"      // cover | contain
}
```

Bilder laddas upp via admin eller via edit-token-URL. Lagring på disk i en volume, inte i databasen.

### 5.5 `iframe` — Embedda extern URL

```json
{
  "url": "https://intra.svenskakyrkan.se/nagot",
  "refresh_seconds": 300,
  "scroll": false
}
```

Observera: många interna system sätter X-Frame-Options / CSP som blockerar iframe. Widget-editorn bör **testa URL:en med en HEAD/GET-förfrågan och varna om frame-ancestors inte tillåts**, så att användaren inte blir förvirrad av en blank ruta.

### 5.6 `clock` — Klocka/datum

```json
{
  "format": "time_date",    // time_only | date_only | time_date | day_time
  "timezone": "Europe/Stockholm",
  "locale": "sv_SE",
  "size": "xl"
}
```

Rent klientsidigt. **Viktigt**: hämta `new Date()` vid varje render-tick snarare än att räkna upp från en sparad variabel — webbläsartimers driftar över tid, särskilt på lågpresterande hårdvara. Uppdatera endast `textContent` på befintlig DOM-nod (ingen `innerHTML`-reflow).

### 5.7 `raw_html` — Godtycklig HTML (admin-only)

Felsökningsverktyg. Admin kan slänga in HTML direkt utan att skapa en ny widget-typ. **Ingen edit-token tillåts på den här typen** — godtycklig HTML är en XSS-vektor om den delegeras.

```json
{
  "html": "<div style='…'>…</div>",
  "css": "/* optional custom CSS */"
}
```

Användbart när något är trasigt i produktion och man snabbt vill testa en hypotes, eller för engångs-saker som inte är värda en full widget-typ.

### 5.8 `debug` — Systemstatus-widget

Liten widget som visar skärmens identitet och läge. Aktiveras via query-param `?debug=1` på kioskvyn eller kan placeras permanent i en vy för on-site-felsökning.

Visar:
- Skärmens namn och slug
- Nuvarande vy-position och totalt antal vyer
- Tid sedan senaste SSE-event (kritiskt för att se om anslutningen är hälsosam)
- Tid sedan senaste sidladdning
- Antal reconnects sedan sidladdning
- Version/commit-hash av tjänsten

Ingen konfig behövs. Typiskt placerad i ett hörn med liten typografi.

---

## 6. URL-struktur

### Publika (kioskvyn)

- `GET /s/<slug>` — kioskvyn: server renderar alla vyer i ett dokument, klienten roterar.
- `GET /s/<slug>/view/<n>` — direktlänk till en specifik vy, främst för felsökning.
- `GET /s/<slug>/events` — SSE-endpoint för realtidskommandon (reload, goto_view, etc).
- `GET /api/widget/<id>/data` — JSON/HTML-fragment som klienten `fetch`:ar vid `widget_updated`-event.
- `GET /uploads/<filename>?w=<N>&h=<N>&fmt=<webp|jpeg>` — statiska uppladdade filer med valfri server-side resize (Pillow, cachad på disk).

### Admin (lösenordsskyddad)

- `GET /admin/` — dashboard med alla skärmar, live-status (ansluten/frånkopplad via SSE) och heartbeat-ålder.
- `GET /admin/screens/<id>` — redigera en skärm och dess vyer.
- `POST /admin/screens/<id>/reload` — pusha `reload`-event till alla anslutna klienter för denna skärm.
- `POST /admin/screens/<id>/goto/<position>` — tvinga en specifik vy att visas nu.
- `GET /admin/views/<id>` — redigera en vys layout och widgets.
- `GET /admin/views/<id>/schedules` — hantera schemaläggning för en vy (när den ska visas).
- `GET /admin/widgets` — widget-bibliotek.
- `GET /admin/widgets/<id>` — admin-redigering av widget (fullständig åtkomst).
- `GET /admin/widgets/<id>/history` — revisionshistorik för widgeten.
- `POST /admin/widgets/<id>/revert/<revision_id>` — återställ till en tidigare version.
- `GET /admin/export` — ladda ner hela konfigurationen som YAML (skärmar, vyer, widgets, scheman). Inkluderar inte uploads eller edit-tokens.
- `POST /admin/import` — ladda upp YAML och merga in. Varnar för konflikter innan commit.
- `GET /admin/alerts` — larm-konfiguration (vart ska notiser gå, hur lång tystnad innan larm).
- Varje widget-sparningshandling triggar automatiskt en `widget_updated`-event till skärmar som visar widgeten.

### Edit-token (delegerad redigering)

- `GET /edit/<edit_token>` — redigeringsvy för en widget baserat på dess token. Ingen inloggning krävs.
- `POST /edit/<edit_token>` — spara ändringar. Triggar automatiskt `widget_updated`-event till skärmar som visar widgeten → kyrkogårdschefen ser sina ändringar i princip direkt på den fysiska skärmen.

Token är alltså **per widget**, inte per användare. Om en token komprometteras kan admin rotera den i admin-vyn (genererar ny token, gamla URL:en slutar fungera).

---

## 7. Autentisering och åtkomstkontroll

**Admin-login**: enkel lösenordsbaserad inloggning (bcrypt i DB, eller en `ADMIN_PASSWORD_HASH` i env för v1). Session-cookie med `HttpOnly`, `Secure`, `SameSite=Lax`. **Inte JWT** — onödigt komplext för en enanvändartjänst.

**Edit-token**: långa slumpade strängar (`secrets.token_urlsafe(32)` → ~43 tecken). URL:en är hemligheten.

Säkerhetsöverväganden givet din bakgrund från HR+/Medvind-granskningarna:

- Cookies alltid `HttpOnly` och `Secure`. Ingen session-token i JS-åtkomlig storage.
- CSRF-skydd på alla POST i både admin och edit-vyn (FastAPI har inte inbyggt — använd `fastapi-csrf-protect` eller double-submit-cookie manuellt).
- Rate limiting på `/edit/*` och admin-login (t.ex. `slowapi`).
- **`Referrer-Policy: no-referrer` på alla `/edit/*`-responser.** Annars läcker edit-token via HTTP Referer-headern om användaren klickar en extern länk i markdown-preview eller liknande. Detta är en reell läcka för capability-URL-modellen.
- Inga tokens i query-parametrar i loggade URL:er. Edit-token är i path (`/edit/<token>`), vilket fortfarande hamnar i access-loggar — konfigurera Caddy att inte logga path för `/edit/*`, alternativt scrubba.
- CSP-header som förbjuder extern JS utom den man uttryckligen vill ha.
- Inga third-party-scripts alls i kioskvyn om det går att undvika.

---

## 8. Kioskvy-arkitektur

Kioskvyn är en **minimal vanilla-JS SPA** optimerad för långtidskörning utan minnesläckor. Ingen HTMX, ingen Tailwind, inga tunga bibliotek — total kontroll över DOM:en.

### 8.1 Varför en enhetlig klient (inte två lägen)

Tidigare versioner av denna plan hade ett separat `light`-läge med MPA-navigering för Pi Zero W. Det är bortflyttat från v1 av två skäl:

1. Att underhålla två renderings-pipelines dubblar komplexitet för marginell vinst.
2. Om Pi Zero W (ARMv6) visar sig för svag löses det genom hårdvaruuppgradering till **Pi Zero 2 W** (ARMv7, samma formfaktor, ~200 kr mer, avsevärt bättre Chromium-prestanda) — inte genom att skriva om koden.

Fältet `performance_mode` finns kvar i datamodellen som framtida flagga — om ett behov av MPA-variant faktiskt uppstår kan vi lägga till det som ren render-alternativ utan schemabrytning.

### 8.2 Klientarkitektur

Server renderar alla vyer i en sida som `<div class="view" data-position="N">`. En minimal vanilla-JS-snutt (<100 rader):

- Roterar synlighet med CSS-klasser (opacity-transition, inte display:none — undviker layout-reflow).
- Öppnar en `EventSource` mot `/s/<slug>/events`.
- Vid `widget_updated`: gör en `fetch()` mot widgetens data-endpoint och uppdaterar endast `textContent`/`innerHTML` på specifik nod. Inga globala DOM-rewrites.
- Vid `config_changed`: sätter en flag som triggar reload vid nästa vy-byte.
- Vid `reload`/`goto_view`: agerar direkt.

Minnessnål design: inga closures över stora objekt, inga växande arrays, ingen event listener-ackumulation. Vid vy-byten återanvänds samma DOM-noder, aldrig skapas nya.

### 8.3 Realtidskommunikation: Server-Sent Events

Servern pushar JSON-kommandon via `/s/<slug>/events`:

```json
{"type": "reload"}
{"type": "goto_view", "position": 2}
{"type": "widget_updated", "widget_id": 42}
{"type": "config_changed"}
```

**Varför SSE och inte WebSocket?** Enkelriktat (server→klient), inbyggd auto-reconnect i `EventSource`, trivialt i FastAPI via `sse-starlette`. WebSocket vore onödig komplexitet.

**Backpressure-skydd på servern**: varje klient har en `asyncio.Queue(maxsize=10)`. Vid `put_nowait` som kastar `QueueFull` (klient konsumerar inte i takt — t.ex. halvt tappad TCP-anslutning) stängs connectionen och queue:n städas bort. Klienten återansluter via `EventSource`-auto-reconnect när den lever igen. Utan denna gräns kan en "slow consumer" läcka minne tills servern OOM:ar.

### 8.4 Nätverksresiliens (kritiskt för v1)

Kyrko-WiFi är ökänt instabilt: tjocka stenväggar, äldre APs, gästnät med portal-redirects. Kioskvyn måste överleva 30+ min nätverksbortfall utan att krascha eller visa dinosaurien.

**Robust SSE-reconnect**:
- `EventSource` återansluter automatiskt, men med exponentiell backoff (1s → 2s → 5s → 15s → 60s, tak vid 60s).
- Logga reconnects diskret i hörnet om `?debug=1` är satt.

**Skydd mot krasch vid fetch-fel**:
- Widget-data-fetches (vid `widget_updated`) måste vara try/catch. Vid fel: behåll befintlig DOM, logga fel, försök igen nästa SSE-tick.
- Vid `config_changed`: **gör inte full reload om nätet är nere**. Chromium hanterar detta dåligt — kan landa på en offline-sida som inte återhämtar sig. Bättre: pausa rotationen, vänta tills SSE återansluter, reload då.
- Heartbeat-detektion klientsidigt: om ingen SSE-event på > 90 sekunder (även keepalive-kommentarer räknas), visa en liten "offline"-indikator i hörnet. Tas bort när SSE är återansluten.

**Server-side keepalive**: skicka en SSE-kommentar (`: keepalive\n\n`) var 30:e sekund i varje connection. Både för att hålla proxier från att timea ut och för att klienten ska kunna upptäcka död anslutning.

### 8.5 Widget-rendering

Varje widget-typ implementerar `render(widget, context) -> str`. Kontext innehåller skärmens dimensioner så att bildwidgets kan begära rätt storlek:

```
GET /uploads/<id>?w=1920&h=1080&fmt=webp
```

Servern gör server-side resize med Pillow, cachar resultatet på disk, levererar WebP när browsern stödjer det.

### 8.6 Touch-stöd

CSS `overflow-y: auto` + `touch-action: pan-y` på scrollbara widgets. Ingen egen gest-hantering.

### 8.7 Offline-tolerans (v1-nivå)

Det som levereras i v1 — *utan* service worker eller IndexedDB:

- ICS-data cachas server-side, så om en ICS-URL är otillgänglig visar widgeten senaste kända data med stale-indikator (`"Uppdaterad 14:32"`).
- Vid komplett nätverksbortfall: klienten behåller senast renderade HTML i minnet. Rotation fortsätter. Klockan tickar. Stale-banner visas.
- Visa **aldrig** en blank widget eller Chromiums offline-sida.

Fullständig service-worker-cache med IndexedDB kommer i fas 5 om behovet kvarstår efter fälttest.

---

## 9. Deploy — två varianter

Eftersom du inte bestämt var tjänsten ska köras skissar jag båda. Grunden (kod, docker-compose) är identisk.

### Variant A: Hetzner Cloud (som kortlinken)

```
┌───────────────────────────────────────────┐
│  Hetzner CX22 (eller liknande)            │
│  ┌─────────────────────────────────────┐  │
│  │ Caddy  → skarmar.svky.se (TLS)      │  │
│  └──────────────┬──────────────────────┘  │
│                 │                          │
│  ┌──────────────▼──────────────────────┐  │
│  │ FastAPI-container (uvicorn)         │  │
│  │   - SQLite i /data/skarmar.db       │  │
│  │   - Uploads i /data/uploads/        │  │
│  └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

- Fördel: externt nåbar utan VPN, RPi:na kan peka direkt på `https://skarmar.svky.se/s/<slug>`.
- Nackdel: interna ICS-kalendrar (om de ligger bakom Svenska kyrkans intranät) behöver antingen publiceras externt eller hämtas via en relä på jobbet.
- Backup: daglig `sqlite3 .backup` till Hetzner Storage Box, eller enkel volym-snapshot.

### Variant B: Intern server på jobbet

```
┌───────────────────────────────────────────┐
│  Intern Linux-server (eller Unraid)       │
│  ┌─────────────────────────────────────┐  │
│  │ Caddy  → skarmar.internt.svky.se    │  │
│  │         (internt CA eller Let's Encrypt via DNS-challenge) │
│  └──────────────┬──────────────────────┘  │
│                 │                          │
│  ┌──────────────▼──────────────────────┐  │
│  │ FastAPI-container                   │  │
│  └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

- Fördel: interna kalendrar och intranät-iframes fungerar rakt av. Data stannar inom infrastrukturen (trevligare ur GDPR-synvinkel även om det här är tjänsteinformation snarare än personuppgifter i stor skala).
- Nackdel: RPi:na måste vara på samma nät eller nå servern via VPN. Certifikathantering är mer jobbigt om ni inte har ACME via intern DNS.

**Min rekommendation**: börja på Hetzner om ICS-kalendrarna redan har publika (token-skyddade) URL:er. Om de ligger bakom intranät-autentisering är intern drift enklare. Vi kan flytta senare — koden är hostingagnostisk.

---

## 10. Implementationsfaser

### Fas 1 — skelett och nätverksresilient MVP

- [ ] Projektstruktur + docker-compose + Caddy
- [ ] Datamodell + migreringar (Alembic), inkl. `performance_mode`-flagga (reserverat för framtida bruk), `WidgetRevision`, heartbeat-fält på `Screen`, `ViewSchedule` (schema finns, UI kommer senare)
- [ ] Admin-login + session-hantering
- [ ] CRUD för Screen, View, Widget (admin-UI med Jinja + HTMX + Tailwind)
- [ ] **Revisionshistorik från dag ett**: varje widget-save skapar en `WidgetRevision`. Auto-rensning av äldsta när > 20 finns per widget. Visa historik i admin, implementera revert-knapp.
- [ ] Kioskvy (vanilla JS SPA, inga tunga bibliotek i kiosken)
- [ ] SSE-endpoint + anslutningsregister med `maxsize=10`-köer + admin-triggad reload
- [ ] **Robust SSE-reconnect i klienten**: exponentiell backoff, keepalive-detektion, pausa rotation vid nätfel istället för att reload:a till offline-sida
- [ ] Server-side SSE keepalive var 30:e sekund
- [ ] Referensintegritet för widgets i `layout_json` (DELETE-check + "Widget saknas"-placeholder vid render)
- [ ] Widget-typ: `markdown` (med `nh3`-sanitering)
- [ ] Widget-typ: `clock` (new Date() per tick, textContent-only)
- [ ] Widget-typ: `raw_html` (admin-only, felsökningsverktyg — ingen edit-token)
- [ ] Widget-typ: `debug` (systemstatus, aktiveras via `?debug=1` eller placering i vy)
- [ ] Edit-token-flöde för markdown-widget (inkl. auto-push vid spara, `Referrer-Policy: no-referrer`)
- [ ] Pi bootstrap-script: NTP-sync-vänta innan Chromium startar (Pi saknar RTC)
- [ ] Testa på Pi 4 (primär) och Pi Zero 2 W (sekundär). Pi Zero W (ARMv6) är stretch-goal — om det krånglar är rekommendationen att uppgradera till Zero 2 W, inte att bygga ett light-läge.

Milstolpe: kyrkogårdschefens infosida kan administreras via token-URL, dyker upp på skärmen inom sekunder efter spara, överlever 30 min WiFi-bortfall utan krasch, och gamla versioner kan återställas.

### Fas 2 — kalendrar och drift-observabilitet

- [ ] `ics_list`-widget med server-side cache och RRULE-expansion
- [ ] Multi-källa-stöd (flera ICS-URL:er i samma lista, färgkodade)
- [ ] `ics_month`-widget
- [ ] Bakgrundsjobb (asyncio-loop med try/except) som refreshar alla ICS-cachar var 10:e minut
- [ ] Felhantering + senast-uppdaterad-indikator per widget
- [ ] **Heartbeat-logik**: skärmar uppdaterar `last_seen_at` på `Screen` via SSE-keepalive
- [ ] **Live-status på admin-dashboard**: grön/gul/röd indikator baserad på heartbeat-ålder
- [ ] **Larm vid död skärm**: när heartbeat > 15 min, skicka notis via konfigurerbar kanal (mail via SMTP, eller webhook → gotify/pushover/discord). `alert_sent_at` förhindrar spam.

Milstolpe: vaktmästeri-skärmen och domprostens namnskylt är i drift. Du får mail om en skärm slutar svara.

### Fas 3 — resterande widgets och drift-ergonomi

- [ ] `slideshow` med uppladdning + server-side resize och on-disk-cache (Pillow)
- [ ] `iframe` med CSP-förhandstest (HEAD/GET-kontroll + varning om `frame-ancestors` blockerar)
- [ ] Förhandsvisning i admin (rendera vyn i en liten ram)
- [ ] Rotera edit-tokens från admin
- [ ] Admin-lösenord i DB istället för env (så det går att byta utan restart)
- [ ] Rate limiting (`slowapi`) + CSRF-skydd (`fastapi-csrf-protect`)
- [ ] Backup-rutin dokumenterad (SQLite `.backup` + uploads-tarball)
- [ ] **Export/import av konfiguration** som YAML. Git-kompatibelt, versionskontrollbart.
- [ ] Belastningstest: Pi 4 48 h utan omstart + Pi Zero 2 W om den används

Milstolpe: hela konfigurationen kan versionshanteras i git. Alla widget-typer finns.

### Fas 4 — schemaläggning

- [ ] UI för `ViewSchedule`: admin kan sätta vyer att visas under specifika perioder
- [ ] Cron-parsing + evaluering vid vy-rotation i servern
- [ ] Vyer utan aktiva scheman visas alltid (baseline); vyer med scheman visas endast när någon regel matchar
- [ ] Visualisering av kommande schemaläggningar i admin ("Denna vy visas 23–26 december")

Milstolpe: "påskvyn" och "julvyn" kan sättas upp i förväg.

### Fas 5 — utökad offline-tolerans (om det behövs)

Fas 1 levererar redan grundläggande resiliens (stale ICS-data, ingen reload vid nätfel, stale-indikator). Denna fas läggs endast till om fälttest visar att det inte räcker.

- [ ] Service worker i kioskvyn som cachar senaste renderade vyer
- [ ] IndexedDB-lagring av senaste HTML per vy
- [ ] Fallback till cache vid komplett sidladdningsfel
- [ ] Separat test-scenario för "vaktmästeriets WiFi dör i 4 timmar"

Milstolpe: en skärm som tappar nät i timmar visar cachad innehåll istället för Chromium-felsida.

### Fas 6 — skärm-hårdvarukontroll

- [ ] HDMI-CEC-integration: stäng av skärm (inte bara svart innehåll) kvällstid
- [ ] Cron-jobb på Pi:n eller server-push via SSE-event (`{"type": "display_power", "state": "off"}`)
- [ ] Schema per skärm (vaktmästeriets skärm kan släckas 18:00–06:00, domprostens lyser under arbetstid)

Milstolpe: skärmar stängs av nattetid — sparar el, förlänger skärmens livslängd, stör inte mörka lokaler.

### Fas 7 — bonus/framtid

- [ ] SSO mot Svenska kyrkans IdP (ersätter admin-lösenord, kompletterar inte edit-tokens)
- [ ] Widget-typ för Medvind-data (om det blir aktuellt — kräver API-åtkomst)
- [ ] Eventuellt `light`-läge (MPA-navigering) om hårdvaruproblem uppstår som inte löses av Zero 2 W-uppgradering
- [ ] Multi-språk i admin (om behov dyker upp)
- [ ] Push-targets: webhook till Microsoft Teams om ni börjar använda det internt

---

## 11. Kiosk-setup på Raspberry Pi

### 11.1 Gemensamt (alla Pi-modeller)

- **OS**: Raspberry Pi OS Lite — ingen desktop environment, manuell X + Chromium-uppsättning.
- **Browser**: Chromium i `--kiosk`-läge.
- **Autostart**: systemd-user-service som startar Chromium efter auto-login.
- **Skärmsläckare/energisparläge av**: `xset s off` + `xset -dpms` i startskriptet.
- **URL**: `https://skarmar.svky.se/s/<slug>`.
- **NTP-väntan innan Chromium startar**: Pi:er saknar RTC (Real Time Clock). Vid uppstart utan nät tror de att det är 1970, vilket får alla ICS-kalendrar att bete sig felaktigt och ger tokens konstiga expiry-datum. Bootstrap-skriptet ska köra `systemd-timesync-wait` eller motsvarande (`chronyc waitsync 10` funkar också) innan Chromium lanseras.

### 11.2 Pi 3 / 4 / 5 (primär målhårdvara)

Standard Chromium-flaggor, ingen speciell tuning:

```
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  https://skarmar.svky.se/s/<slug>
```

Har råd med 64-bit OS och 5 GHz WiFi.

### 11.3 Pi Zero 2 W (rekommenderat om liten formfaktor behövs)

ARMv7, 512 MB RAM, men avsevärt bättre Chromium-prestanda än Zero W. Samma flaggor som Pi 3+:

```
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --disk-cache-size=50000000 \
  https://skarmar.svky.se/s/<slug>
```

32-bit eller 64-bit OS fungerar. 2.4 GHz WiFi.

### 11.4 Pi Zero W (stretch-goal, inte rekommenderad)

ARMv6, 512 MB RAM. Chromium fungerar men är långsam och i långsam utfasning av Chromium-projektet.

**Mitt råd**: undvik om möjligt. Pi Zero 2 W är samma formfaktor, ~200 kr mer, och undanröjer hela kategorin av problem. Om du ändå vill använda befintliga Zero W-enheter:

```
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --disable-translate --disable-features=TranslateUI \
  --disk-cache-size=1 --media-cache-size=1 \
  --process-per-site \
  https://skarmar.svky.se/s/<slug>
```

Ytterligare:
- 32-bit OS (krav för ARMv6).
- Använd A2-klassat SD-kort eller helst USB-SSD — ökat swap-tryck sliter vanliga SD-kort.
- Håll swap rimlig (512 MB), inte 1 GB — mer swap uppmuntrar bara mer swappande.
- Testa att faktiska vyer fungerar under 48h innan produktionssättning.

Om prestandan är otillräcklig eller stabiliteten dålig: uppgradera till Zero 2 W (200 kr och en fredag att växla över). Fas 7 har `light`-läge som teoretisk fallback men bör inte byggas förrän det är bevisat nödvändigt.

### 11.5 Bootstrap-script

Ett kort ansible-playbook eller bash-skript som bootstrappar en ny Pi (detekterar modell, väljer rätt flaggor, sätter upp autostart, väntar på NTP) läggs i repot under `deploy/kiosk-setup/`.

---

## 12. Öppna frågor att besvara innan bygget börjar

1. **Hosting-beslut**: vilket nät ligger ICS-kalendrarna på? Det avgör Hetzner vs intern drift. Om kalendrarna är bakom intranät-autentisering blir intern drift betydligt enklare.
2. **Domän**: ska det ligga under `svky.se` (som kortlinken) eller under svenska kyrkans huvuddomän? Påverkar cert-setup och intern brandvägg.
3. **Backup-strategi**: hur ofta, vart, hur länge? Sannolikt räcker daglig SQLite-dump + uploads-tarball i 30 dagar.
4. **Larm-kanal**: mail via SMTP, eller en av gotify/pushover/discord/Teams? Påverkar integration i fas 2.
5. **Befintliga Pi Zero W-enheter**: hur många finns, vilka används till vad? Ska kartläggas så det är tydligt vilka som kan behöva uppgraderas till Zero 2 W.

---

## 13. Kompletterande anteckningar för Claude Code

- Använd `uv` för dependency-hantering (snabbare än pip, samma som kortlinken förhoppningsvis).
- All kod med typannoteringar, `mypy --strict` i CI.
- Tester: `pytest` med `httpx.AsyncClient` för endpoint-tester. Prioritera integrationstester över enhetstester för en tjänst av den här storleken.
- Loggning: structured JSON till stdout, läses av Docker-loggar. Inget eget loggrotations-system.
- Inga secrets i koden. Allt via env-variabler, dokumenterade i `.env.example`.
- README ska innehålla: quick start lokalt, deploy till prod, hur man tar backup, hur man roterar edit-tokens.
