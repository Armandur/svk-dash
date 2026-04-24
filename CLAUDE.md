# skarmar – kodbasbeskrivning för Claude

## Vad projektet är

Intern informationsskärm-tjänst för Svenska kyrkan. Ersätter Dakboard. En skärm = en URL som körs i kiosk-läge på Raspberry Pi. Skärmar roterar mellan layouter och vyer med widgets (ICS-kalender, markdown, klocka m.m.). Admin redigerar allt via webbgränssnitt; delegerade redaktörer via hemliga token-URL:er.

## Stack

- **Python 3.12 + FastAPI** (ASGI, uvicorn)
- **SQLModel** (SQLAlchemy + Pydantic) med SQLite och WAL-läge
- **Alembic** för migrationer
- **Jinja2** för templating (server-side rendering)
- **HTMX + Tailwind CDN** i admin-UI
- **Vanilla JS** i kioskvyn (inga tunga bibliotek, ~650 rader)
- **SSE (sse-starlette)** för realtids-push till skärmar
- **Caddy** som reverse proxy
- **uv** för dependency-hantering

## Filstruktur

```
app/
  main.py              # FastAPI-app, lifespan, mounts, middleware
  config.py            # Miljövariabler och konstanter
  database.py          # SQLModel engine, WAL-pragma, get_session()
  models.py            # Alla SQLModel-modeller
  auth.py              # Session-cookies (itsdangerous), verify_password (bcrypt)
  deps.py              # require_admin() FastAPI-beroende
  templating.py        # Jinja2-instans + filter (tojson, schedule_summary, now_local)
  sse.py               # SSE-registry: register/unregister/broadcast per screen_id
  routes/
    admin/
      __init__.py      # Kombinerar submodulernas routers under /admin
      auth.py          # GET/POST /admin/login, POST /admin/logout
      channels.py      # Channel CRUD, layout-tilldelningar, zon-/vy-CRUD per kanal
      screens.py       # Screen CRUD, kanal-väljare, batchåtgärder
      views.py         # GET/POST /admin/views/<id> — widget-layout i vy
      widgets.py       # Widget CRUD, revisionshistorik, token-rotering
      layouts.py       # Layout CRUD, zon-editor (drag/resize)
      media.py         # Mediebibliotek: uppladdning, mappar, radering
      sse_control.py   # Admin-triggered SSE-events (reload m.m.)
    edit.py            # GET/POST /edit/<token> — delegerad redigering
    kiosk.py           # Kiosk-endpoint, SSE, widget-API, broadcast-funktioner
  widgets/             # En fil per widget-typ
    base.py            # render_widget() dispatcher
    clock.py
    color_block.py
    debug.py
    ics_common.py      # Delad ICS-parsning och filtrering
    ics_list.py
    ics_month.py
    ics_schedule.py
    ics_week.py
    image.py
    markdown.py
    raw_html.py
    slideshow.py
    text.py
  services/
    ics_fetcher.py     # Bakgrundsjobb: hämtar ICS var 10:e min, deduplicerat
    layout_scheduler.py
    screen_monitor.py
  templates/
    admin/
      base.html        # Nav, Tailwind CDN, HTMX CDN
      login.html
      index.html       # Dashboard (skärmlista)
      screens.html
      screen_form.html
      screen_detail.html  # Skärm: kanal-väljare, hårdvaruinställningar, diagnostik
      channel_detail.html # Kanal: layout-tilldelningar, zon-/vy-hantering, kopplade skärmar
      channel_form.html   # Formulär för skapa/redigera kanal
      channels.html       # Kanallista
      zone_detail.html    # Zon: vylista med schema/transition per vy
      view_detail.html    # Vy: widget-layout editor
      widget_detail.html  # Widget: konfig, revisionshistorik, edit-token
      widget_form.html
      widgets.html
      layout_detail.html  # Layout: zon-editor (drag/resize)
      layout_form.html
      layouts.html
      media.html          # Mediebibliotek: grid/list, mappar, batch-operationer
      _schedule_modal.html  # Delad modal för schema + transition + enabled
    kiosk/
      screen.html      # Kiosk-vy: alla layouter pre-renderade, JS-konstanter
  static/
    kiosk.js           # Kiosk-klient (~650 rader, vanilla JS)
data/                  # SQLite-DB och uploads (gitignorerat)
alembic/               # Migrationer
deploy/
  kiosk-setup/         # Bootstrap-script för RPi
```

## Datamodell

### Hierarki
```
Screen (slug, URL, hårdvara)
  └── channel_id → Channel (logisk konfiguration)
                     └── ChannelLayoutAssignment (enabled, schedule_json, duration_seconds,
                     │                            transition, transition_direction,
                     │                            transition_duration_ms, priority)
                     │     └── Layout
                     │           └── LayoutZone (role, x/y/w/h_pct, rotation_seconds,
                     │                           transition, transition_direction,
                     │                           transition_duration_ms)
                     │                 └── View (enabled, schedule_json, duration_seconds,
                     │                           transition, transition_direction,
                     │                           transition_duration_ms, layout_json)
                     │                       └── Widget (via layout_json, eller inline)
                     └── ZoneWidgetPlacement (för persistenta zoner)
```

### Screen vs Channel
- **Screen** = fysisk enhet med slug/URL. Pekar på en kanal via `channel_id` (nullable).
  Flera skärmar kan dela samma kanal. En skärm utan kanal visar tom kiosk.
- **Channel** = logisk konfiguration: layouter, zoner, vyer. Kan existera utan kopplade
  skärmar (förbered innehåll innan hårdvaran finns). `broadcast_widget_updated` och
  schema-ändringar broadcastar till alla screens med det channel_id.

### Modeller (models.py)
- **Channel** – name, description; äger all innehållskonfiguration
- **Screen** – slug, name, channel_id (FK→Channel), show_offline_banner, last_seen_at, last_connection_count, alert_sent_at
- **ChannelLayoutAssignment** – kopplar kanal till layout; enabled, schedule_json, duration_seconds, transition, transition_direction, transition_duration_ms, priority
- **Layout** – återanvändbar mall; name, description, aspect_ratio
- **LayoutZone** – yta i procent; role (persistent/schedulable), rotation_seconds, transition, transition_direction, transition_duration_ms
- **View** – channel_id, zone_id, position, enabled, schedule_json, duration_seconds, transition, transition_direction, transition_duration_ms, layout_json (widget-placeringar)
- **Widget** – kind, name, config_json, edit_token
- **ZoneWidgetPlacement** – widget i persistent zon; channel_id (nullable = template-default), widget_id eller inline_kind, config_json, x/y/w/h, z_index, opacity
- **IcsCache** – widget_id + source_url → raw_ics, etag, fetched_at
- **WidgetRevision** – historik per widget (max 20), config_json, saved_via
- **MediaFolder** / **MediaFile** – mediebibliotek; filename (UUID på disk), original_name
- **LayoutRevision** – historik per layout

### Arvslogik för transition
Vyer ärver transition-inställningar från sin zon om egna fält är `None`. Kiosk.js: `nextView.transition || zone.transition || 'fade'`. Samma mönster för transition_direction och transition_duration_ms.

### enabled + schedule_json
Båda finns på `ChannelLayoutAssignment` och `View`.
- `enabled=False` → filtreras bort helt vid kiosk-rendering (server-side)
- `schedule_json` → utvärderas client-side i kiosk.js för vy-rotation, server-side i `_is_active()` för layout-val och admin-preview

## URL-struktur

### Admin (lösenordsskyddat)
```
GET  /admin/                                              # Dashboard
GET  /admin/screens                                       # Skärmlista (med batch-kanal-val)
GET  /admin/screens/new
POST /admin/screens/<id>/edit                             # name, slug, channel_id, show_offline_banner
POST /admin/screens/<id>/delete
GET  /admin/screens/<id>                                  # Kanal-väljare + hårdvaruinställningar
POST /admin/screens/batch-assign-channel                  # Tilldela kanal till flera skärmar

GET  /admin/channels                                      # Kanallista
GET  /admin/channels/new
POST /admin/channels/new
GET  /admin/channels/<id>?sel=<assignment_id>             # Kanal + layout-tilldelningar + zoner
POST /admin/channels/<id>/edit
POST /admin/channels/<id>/delete
POST /admin/channels/<id>/layout/assign                   # Koppla layout till kanal
POST /admin/channels/<id>/layout/<aid>/schedule           # Schema + transition + enabled
POST /admin/channels/<id>/layout/<aid>/remove
GET  /admin/channels/<id>/zones/<zid>                     # Zon-detalj: vyer i zonen
POST /admin/channels/<id>/zones/<zid>/settings            # rotation_seconds, transition...
POST /admin/channels/<id>/zones/<zid>/views/new
POST /admin/channels/<id>/zones/<zid>/views/<vid>/schedule  # Schema + transition + enabled
POST /admin/channels/<id>/zones/<zid>/views/<vid>/detach
POST /admin/channels/<id>/zones/<zid>/views/<vid>/delete

GET  /admin/views/<id>                                    # Widget-layout editor
POST /admin/views/<id>/edit
GET  /admin/widgets
GET  /admin/widgets/new
GET  /admin/widgets/<id>
POST /admin/widgets/<id>/edit
POST /admin/widgets/<id>/rotate-token
POST /admin/widgets/<id>/revert/<rev_id>
POST /admin/widgets/<id>/delete
GET  /admin/layouts
GET  /admin/layouts/new
GET  /admin/layouts/<id>
POST /admin/layouts/<id>/edit
POST /admin/layouts/<id>/delete
GET  /admin/media
POST /admin/media/upload
POST /admin/media/folders/new
POST /admin/media/move
POST /admin/media/delete
```

### Edit-token (delegerad redigering)
```
GET  /edit/<token>
POST /edit/<token>
```

### Kiosk
```
GET  /s/<slug>                   # Kiosk-vy (alla aktiva layouter pre-renderade)
GET  /s/<slug>/events            # SSE-endpoint
GET  /api/widget/<id>/data       # Widget-HTML för live-uppdatering
```

## Kiosk-klientens arkitektur (kiosk.js)

All HTML renderas server-side vid sidladdning. Klienten hanterar sedan:

**JS-konstanter (injiceras i screen.html):**
```javascript
const SCREEN_SLUG         = "vaktmasteriet";
const KIOSK_LAYOUTS       = [...];  // Metadata utan widget-HTML
const LAYOUT_ROTATION     = { duration_seconds, transition, transition_direction, transition_duration_ms };
const SHOW_OFFLINE_BANNER = true;
```

**Rotation:**
- `rotateLayout()` – växlar mellan `div.layout-panel`-element i DOM; fade/slide/none med riktning
- `scheduleZone(zoneId)` – roterar vyer inom en zon baserat på duration och schedule_json
- `showZoneView(zoneId, idx)` – animerar vy-övergång (slide med CSS-animationer scoped till zonen, fade med opacity)

**SSE:**
- `connectSSE()` – ansluter till `/s/<slug>/events`, reconnect med exponential backoff
- `reload`-event → `location.reload()`
- `widget_updated`-event → hämtar `/api/widget/<id>/data`, ersätter DOM-nod

**Offline-resiliens:**
- Separat `isOffline`-flagga (inte `isPaused`) — rotation och klockor fortsätter vid tappad SSE
- Offline-banner visas bara om `SHOW_OFFLINE_BANNER === true`
- Timeout: 90 sekunder utan event → markeras offline

## Viktiga designbeslut

- **Alla layouter pre-renderas** i DOM vid sidladdning — layout-rotation sker client-side utan `location.reload()`. Layouter visas/döljs med CSS.
- **Screen/Channel-separation**: Fysiska skärmar (slug/URL) är löst kopplade till logiska kanaler (innehåll). En kanal kan delas av flera skärmar; byta kanal på en skärm kräver inget omstart av kiosk. SSE-registry är fortfarande per screen_id (inte channel_id) eftersom det är det fysiska lagret som håller anslutningen.
- **Widget-referensintegritet**: `layout_json` på `View` innehåller widget-IDs utan formell FK. Vid DELETE-försök returnerar servern 409 om widgeten används; `?force=1` städar referenserna. Vid render: saknad widget → placeholder, inte krasch.
- **Revisioner**: varje widget-save skapar `WidgetRevision`. Auto-rensning: max 20 per widget.
- **raw_html-widget**: ingen edit-token (XSS-risk vid delegering). Admin-only.
- **SSE-backpressure**: `asyncio.Queue(maxsize=10)` per klient. `QueueFull` → koppla ned.
- **Session**: itsdangerous `URLSafeTimedSerializer`, HttpOnly cookie, SameSite=Lax.
- **Lösenord**: `ADMIN_PASSWORD_HASH` i env (bcrypt). Ingen DB-tabell.
- **Referrer-Policy: no-referrer** på `/edit/*`-svar (capability URL — token läcker via Referer annars).
- **ICS-deduplicering**: `ics_fetcher.py` gör en HTTP-request per unik URL oavsett hur många widgets som delar källan.

## Fallgropar

### tojson i onclick-attribut
`templating.py`-filtret `tojson` gör `Markup(json.dumps(...))` — HTML-escapar INTE `"`. Tomma strängar renderas som `""` och bryter `onclick="..."`. **Lösning:** använd single-quoted JS-strängar i onclick för strängvärden: `transition: '{{ view.transition or '' }}'` — inte `tojson`.

### Tomma heltalsfält i formulär
Webbläsare skickar tomma fält som `""`, inte som frånvaro. FastAPI kan inte parsa `""` som `int | None`. **Lösning:** deklarera som `str | None = Form(None)` och konvertera manuellt: `int(v) if v else None`.

### Alembic + SQLite NOT NULL
SQLite tillåter inte `ALTER TABLE ADD COLUMN ... NOT NULL` utan `server_default`. Lägg alltid till `server_default='...'` i migrationer för icke-nullbara kolumner på befintliga tabeller.

## Statusindikatorer (admin-UI)

Konsekvent prickdesign på layouter och vyer:
- **Fylld grön** (`bg-green-400`) – aktiverad och aktiv nu (ingen schema eller schemat matchar)
- **Kontur grön** (`border-2 border-green-400`) – aktiverad men visas ej pga schema
- **Röd** (`bg-red-400`) – inaktiverad (`enabled=False`)

## Miljövariabler

| Variabel | Beskrivning |
|----------|-------------|
| `SECRET_KEY` | Signeringsnyckel för cookies |
| `ADMIN_PASSWORD_HASH` | bcrypt-hash av adminlösenord |
| `DATABASE_PATH` | Sökväg till SQLite, default `data/skarmar.db` |
| `UPLOADS_DIR` | Uppladdningsmapp, default `data/uploads` |
| `BASE_URL` | Publik URL utan slash, t.ex. `https://skarmar.svky.se` |
| `SESSION_COOKIE_NAME` | Default `session` |

## Köra lokalt

```bash
uv sync
uv run alembic upgrade head

# Generera adminlösenord
python3 -c "import bcrypt; print(bcrypt.hashpw(b'ditt-lösenord', bcrypt.gensalt()).decode())"

# Starta dev-server
ADMIN_PASSWORD_HASH='$2b$12$...' uv run uvicorn app.main:app --reload >> dev.log 2>&1 &
tail -f dev.log
```

Loggen skrivs till `dev.log`. Kontrollera alltid den filen vid startproblem.

## Arbetssätt vid större ändringar

När en feature är implementerad och commitad: be användaren testa de påverkade flödena
i webbläsaren medan du kollar dev.log. Formulera en kort lista med konkreta saker att
testa, t.ex. "skapa en kanal, lägg till en layout, öppna /s/<slug>". Gör det parallellt —
läs dev.log medan användaren klickar. Åtgärda fel innan du förklarar något som klart.

Gäller alltid efter: nya admin-sidor, databasmigrationer, refaktoreringar av routes/templates,
ändringar som rör kiosk-rendering.

## Vanliga uppgifter

**Lägga till ett nytt admin-flöde:**
1. Skapa `app/routes/admin/nyttflöde.py` med `router = APIRouter()`
2. Importera och include i `app/routes/admin/__init__.py`
3. Lägg till template i `app/templates/admin/`
4. Länka från nav i `admin/base.html`

**Lägga till en ny widget-typ:**
1. Lägg till kind-strängen i `WIDGET_KINDS` i `app/routes/admin/widgets.py`
2. Skapa renderer i `app/widgets/<kind>.py` med `render(widget, context) -> str`
3. Registrera i `app/widgets/base.py`

**Ny Alembic-migration:**
```bash
uv run alembic revision --autogenerate -m "beskrivning"
# Kontrollera den genererade filen — lägg till server_default vid behov
uv run alembic upgrade head
```

**Verifiera efter ändring:**
```bash
uv run python -c "from app.main import app; print('OK')"
```

**Ruff:**
```bash
uv run ruff check app/ --fix && uv run ruff format app/
```

---

## UI/UX-konventioner

### Knappstilar
- **Primär**: `bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700`
- **Sekundär (Grå)**: `bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded text-sm transition-colors`
- **Destruktiv (Stor)**: `text-sm text-red-600 bg-red-50 hover:bg-red-100 px-3 py-2 rounded transition-colors`
- **Destruktiv (Mini)**: `text-xs text-red-600 bg-red-50 hover:bg-red-100 px-2 py-1 rounded`
- **Länk-knapp (Blå)**: `text-xs text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-1 rounded transition-colors`
- **Länk-knapp (Grå)**: `text-xs text-gray-500 hover:text-gray-900 bg-gray-100 px-2 py-1 rounded`
- **Avbryt**: `text-sm text-gray-600 hover:text-gray-900` (ofta enbart text)

### Formulärelement
- **Input/Select**: `w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500`
- **Etikett (Label)**: `block text-xs font-medium text-gray-600 mb-1`
- **Checkbox**: `rounded border-gray-300 text-blue-600 focus:ring-blue-500`
- **Fältgruppering**: Använd `space-y-4` för vertikal separation mellan fält.

### Kort och Paneler
- **Standardkort**: `bg-white rounded-lg shadow p-5` (använd `rounded-xl` för större ytor)
- **Tomma tillstånd**: `bg-white rounded-lg shadow p-12 text-center` med `text-gray-400`
- **Dashed container**: `py-8 text-center border border-dashed border-gray-200 rounded-lg`

### Rubriker och Etiketter
- **Huvudrubrik**: `text-2xl font-bold mb-6`
- **Kortrubrik**: `font-semibold text-sm mb-3` (ofta inne i en panel)
- **Kategorirubrik**: `text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2`
- **Badges**: `text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded`

### Modaler
- **Overlay**: `fixed inset-0 z-50 flex items-center justify-center` med `background:rgba(0,0,0,0.45)`
- **Struktur**: `bg-white rounded-xl shadow-2xl flex flex-col` (bredd ofta `max-width:440px` eller `560px`)
- **Stängning**: Stäng vid klick på overlay, Escape-tangent eller `&times;`

### Navigering och Layout
- **Navbar**: `bg-white border-b border-gray-200 px-6 py-3`, länkar `text-sm text-gray-600 hover:text-gray-900`
- **Brödsmulor/Tillbaka**: `text-sm text-gray-500 hover:text-gray-900` med pil `←`
- **Sidopanel (Sidoflikar)**: `w-44 border-r border-gray-100 py-3`. Aktiv: `bg-blue-50 text-blue-700 font-semibold`.

### Färgpalett & Feedback
- **Status-prickar**: fylld grön = aktiv nu, kontur grön = schemalagd men ej aktiv, röd = inaktiverad
- **Feedback (Fel)**: `text-sm text-red-600 bg-red-50 rounded px-3 py-2`
- **Editor-vy**: Mörkt tema med `bg-slate-900` (#0f172a), ramar `#334155` och accent `#60a5fa`.
