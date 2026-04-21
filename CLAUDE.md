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
