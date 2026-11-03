from __future__ import annotations

from fastapi import APIRouter, Query

from ..schemas import PreferenceIn
from ..services.events import ensure_session
from ..services.profile import delete_preference, ensure_profile, upsert_preference

router = APIRouter()


@router.get("/profile")
def profile(session_id: str = Query(...)) -> dict:
    ensure_session(session_id)
    return ensure_profile(session_id)


@router.post("/profile/preferences")
def create_or_update_preference(body: PreferenceIn) -> dict:
    ensure_session(body.session_id)
    return upsert_preference(body.session_id, body.model_dump())


@router.delete("/profile/preferences/{preference_id}")
def remove_preference(preference_id: str, session_id: str = Query(...)) -> dict:
    ensure_session(session_id)
    return delete_preference(session_id, preference_id)
