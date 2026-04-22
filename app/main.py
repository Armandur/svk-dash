import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.deps import NotAuthenticatedError
from app.routes.admin import router as admin_router
from app.routes.edit import router as edit_router
from app.routes.kiosk import router as kiosk_router
from app.services.ics_fetcher import start_refresh_loop
from app.services.screen_monitor import start_monitor_loop

logging.basicConfig(level=logging.INFO)
os.makedirs("data/uploads", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(start_refresh_loop()),
        asyncio.create_task(start_monitor_loop()),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.include_router(admin_router)
app.include_router(edit_router)
app.include_router(kiosk_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError):
    return RedirectResponse("/admin/login", status_code=302)


@app.get("/")
async def root():
    return RedirectResponse("/admin/", status_code=302)
