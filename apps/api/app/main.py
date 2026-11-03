from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import database_config, init_db, seed_dev_data
from .routers import debug, decisions, events, media, picki, products, profile, sessions, shopping, taste

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_project_env() -> None:
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_project_env()

logger = logging.getLogger(__name__)
app = FastAPI(title="PickMate Agent Harness API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    seed_dev_data()
    config = database_config()
    logger.warning(
        "PickMate database selected: path=%s source=%s catalog=%s",
        config["path"],
        config["source"],
        config["catalog"],
    )
    from .services.launch_demo import DEMO_SESSION_ID, demo_mode, seed_launch_demo
    if demo_mode():
        try:
            result = await seed_launch_demo(DEMO_SESSION_ID)
            logger.warning("Launch demo ready: session=%s cart=%s", result["session_id"], result["cart_ids"])
        except Exception as exc:
            logger.warning("Launch demo seed skipped: %s", exc)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "database": database_config()}


app.include_router(products.router)
app.include_router(media.router)
app.include_router(sessions.router)
app.include_router(events.router)
app.include_router(picki.router)
app.include_router(shopping.router)
app.include_router(decisions.router)
app.include_router(debug.router)
app.include_router(profile.router)
app.include_router(taste.router)
