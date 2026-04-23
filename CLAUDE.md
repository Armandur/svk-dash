# skarmar – kodbasbeskrivning för Claude

## Vad projektet är

Intern informationsskärm-tjänst för Svenska kyrkan. Ersätter dakboard. En skärm = en URL som körs i kiosk-läge på Raspberry Pi. Skärmar roterar mellan vyer med widgets (ICS-kalender, markdown, klocka m.m.). Admin redigerar allt via webbgränssnitt; delegerade redaktörer via hemliga token-URL:er.

## Stack

- **Python 3.12 + FastAPI** (ASGI, uvicorn)
- **SQLModel** (SQLAlchemy + Pydantic) med SQLite och WAL-läge
- **Alembic** för migrationer
- **Jinja2** för templating (server-side rendering)
- **HTMX + Tailwind CDN** i admin-UI
- **Vanilla JS** i kioskvyn (inga tunga bibliotek)
- **SSE (sse-starlette)** för realtids-push till skärmar
- **Caddy** som reverse proxy
- **uv** för dependency-hantering

## Filstruktur

```
app/
  main.py          # FastAPI-app, lifespan, mounts, exception handlers
  config.py        # Miljövariabler och konstanter
  database.py      # SQLModel engine, WAL-pragma, get_session() contextmanager
  models.py        # Screen, View, Widget, IcsCache, WidgetRevision, ViewSchedule
  auth.py          # Session-cookies (itsdangerous), verify_password (bcrypt)
  deps.py          # require_admin() FastAPI-beroende, NotAuthenticatedError
  templating.py    # Jinja2-instans
  routes/
    admin/
      __init__.py  # Kombinerar submodulernas routers under /admin
      auth.py      # GET/POST /admin/login, POST /admin/logout
      screens.py   # CRUD Screen + View (skapa/redigera/ta bort)
      views.py     # GET/POST /admin/views/<id> — widget-layout i vy
      widgets.py   # CRUD Widget, revisionshistorik, token-rotering
  widgets/         # Widget-renderers (byggs ut i Fas 2+)
  templates/
    admin/
      base.html    # Nav, Tailwind CDN, HTMX CDN
      login.html   # Fristående login-sida
      index.html   # Dashboard (skärmlista)
      screens.html
      screen_form.html
      screen_detail.html  # Skärm + vylista + vy-skapare
      view_detail.html    # Vy + widget-layout
      widgets.html
      widget_form.html
      widget_detail.html  # Konfig-editor + revisionshistorik
  static/
data/              # SQLite-DB och uploads (gitignorerat)
alembic/           # Migrationer
deploy/
  kiosk-setup/     # Bootstrap-script för RPi (byggs i Fas 1 slutet)
```

## URL-struktur

### Admin (lösenordsskyddat)
- `GET /admin/` — dashboard
- `GET /admin/screens` — skärmlista
- `GET /admin/screens/new` — skapa skärm
- `GET /admin/screens/<id>` — skärmdetalj + vyer
- `POST /admin/screens/<id>/edit` — uppdatera skärm
- `POST /admin/screens/<id>/delete` — ta bort skärm
- `POST /admin/screens/<id>/views/new` — skapa vy
- `POST /admin/screens/<id>/views/<id>/delete` — ta bort vy
- `GET /admin/views/<id>` — redigera vy + widgets
- `POST /admin/views/<id>/edit` — uppdatera vy
- `POST /admin/views/<id>/widgets/add` — lägg till widget i vy
- `POST /admin/views/<id>/widgets/<id>/remove` — ta bort widget ur vy
- `GET /admin/widgets` — widget-bibliotek
- `GET /admin/widgets/new` — skapa widget
- `GET /admin/widgets/<id>` — redigera widget + historik
- `POST /admin/widgets/<id>/edit` — spara (skapar revision automatiskt)
- `POST /admin/widgets/<id>/rotate-token` — rotera edit-token
- `POST /admin/widgets/<id>/revert/<rev_id>` — återställ revision
- `POST /admin/widgets/<id>/delete` — ta bort (409 om widget används i vy, `?force=1` rensar)

### Edit-token (delegerad redigering, byggs i Fas 1)
- `GET /edit/<token>` — redigeringsvy utan inloggning
- `POST /edit/<token>` — spara

### Kioskvyn (byggs i Fas 1)
- `GET /s/<slug>` — kioskvyn
- `GET /s/<slug>/events` — SSE-endpoint

## Viktiga designbeslut

- **Widget-referensintegritet**: `layout_json` på `View` innehåller widget-IDs utan formell FK. Vid DELETE-försök returnerar servern 409 om widgeten används; `?force=1` städar referenserna. Vid render: saknad widget → placeholder, inte krasch.
- **Revisioner**: varje widget-save skapar `WidgetRevision`. Auto-rensning: max 20 per widget.
- **raw_html-widget**: ingen edit-token (XSS-risk vid delegering). Admin-only.
- **SSE-backpressure**: `asyncio.Queue(maxsize=10)` per klient. `QueueFull` → koppla ned.
- **Session**: itsdangerous `URLSafeTimedSerializer`, HttpOnly cookie, SameSite=Lax.
- **Lösenord**: `ADMIN_PASSWORD_HASH` i env (bcrypt). Ingen DB-tabell i v1.
- `Referrer-Policy: no-referrer` krävs på `/edit/*`-svar (capability URL — token läcker via Referer annars).

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
# Installera uv om det saknas
curl -LsSf https://astral.sh/uv/install.sh | sh

# Installera beroenden och kör migrationer
uv sync
uv run alembic upgrade head

# Generera adminlösenord
python3 -c "import bcrypt; print(bcrypt.hashpw(b'ditt-lösenord', bcrypt.gensalt()).decode())"

# Starta dev-server
ADMIN_PASSWORD_HASH='$2b$12$...' uv run uvicorn app.main:app --reload
```

## Vanliga uppgifter

**Lägga till ett nytt admin-flöde:**
1. Skapa `app/routes/admin/nyttflöde.py` med `router = APIRouter()`
2. Importera och include i `app/routes/admin/__init__.py`
3. Lägg till template i `app/templates/admin/`
4. Länka från nav i `admin/base.html`

**Lägga till en ny widget-typ:**
1. Lägg till kind-strängen i `WIDGET_KINDS` i `app/routes/admin/widgets.py`
2. Skapa renderer i `app/widgets/<kind>.py` med `render(widget, context) -> str`
3. Importera i kiosk-router (byggs i Fas 1)

**Ny Alembic-migration:**
```bash
uv run alembic revision --autogenerate -m "beskrivning"
uv run alembic upgrade head
```

**Ruff (kör alltid innan commit):**
```bash
uv run ruff check app/ --fix && uv run ruff format app/
```

## Planerad arkitektur: Layout-system

> **Status:** ej påbörjat — designbeslut dokumenterade, implementation i tre steg.

### Koncept

Ett nytt lager ovanför nuvarande Vy-modell. En *Layout* är ett återanvändbart template som delar upp skärmen i namngivna *Zoner*. Varje skärm kopplas till en layout och kan schemalägga byte mellan layouter.

```
Layout  (återanvändbart template)
  └── LayoutZone
        x_pct, y_pct, w_pct, h_pct  ← procent av skärmytan
        role: "persistent" | "schedulable"
        grid_cols, grid_rows          ← zonen har eget grid
        └── ZoneWidgetPlacement       ← templatens default-innehåll (persistent zones)

Screen
  └── ScreenLayoutAssignment          ← vilken layout skärmen kör
        layout_id
        schedule: alltid | veckodagar + tidsintervall
        └── ScreenZoneOverride        ← valfri override av template-default per zon
              zone_id
              └── ZoneWidgetPlacement ← skärmens egna version (ersätter template-default)

View  (nuvarande modell, omdöpt konceptuellt till "ZoneContent")
  zone_binding_id                     ← ersätter screen_id
  └── ViewSchedule                    ← när innehållet visas i zonen
```

### Arvslogik för persistenta zoner

- Ingen `ScreenZoneOverride` → template-defaulten visas
- `ScreenZoneOverride` satt → skärmens version vinner (allt-eller-inget per zon)

Användaren ser det som: *"Använd layout-standard / Anpassa för den här skärmen"*

### Migrationsväg

Befintliga skärmar och vyer migreras automatiskt till en autogenererad default-layout med en enda zon som täcker hela skärmen (`x=0, y=0, w=100, h=100, role=schedulable`). Inget data går förlorat.

### Implementationssteg

1. **Layouts + zon-editor** — DB-modeller, `/admin/layouts`, visuell zon-editor (drag/resize)
2. **Koppla skärmar** — `ScreenLayoutAssignment`, `ScreenZoneOverride`, migration
3. **Schemaläggning** — vy-rotation inom zoner, layout-växling per schema

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
- **Stängning**: Stäng vid klick på overlay, Escape-tangent eller `&times;` ( `text-gray-400 hover:text-gray-700 text-2xl` )

### Navigering och Layout
- **Navbar**: `bg-white border-b border-gray-200 px-6 py-3`, länkar `text-sm text-gray-600 hover:text-gray-900`
- **Brödsmulor/Tillbaka**: `text-sm text-gray-500 hover:text-gray-900` med pil `←`
- **Sidopanel (Sidoflikar)**: `w-44 border-r border-gray-100 py-3`. Aktiv: `bg-blue-50 text-blue-700 font-semibold`.

### Färgpalett & Feedback
- **Status-dots**: `bg-green-500` (online), `bg-yellow-400` (recent), `bg-red-500` (offline)
- **Feedback (Fel)**: `text-sm text-red-600 bg-red-50 rounded px-3 py-2`
- **Editor-vy**: Mörkt tema med `bg-slate-900` (#0f172a), ramar `#334155` och accent `#60a5fa`.
