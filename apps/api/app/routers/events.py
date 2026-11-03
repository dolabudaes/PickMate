from __future__ import annotations

from fastapi import APIRouter

from ..schemas import EventIn
from ..services.events import record_event

router = APIRouter()


@router.post("/events")
def events(body: EventIn) -> dict:
    return record_event(body.session_id, body.name, body.product_id, body.metadata)
