from __future__ import annotations

from fastapi import APIRouter

from ..schemas import SessionCreateOut
from ..services.events import create_session, ensure_session
from ..services.profile import ensure_profile, merge_profile_patch

router = APIRouter()


@router.post("/sessions")
def sessions() -> SessionCreateOut:
    session_id = create_session()
    return SessionCreateOut(session_id=session_id, profile=ensure_profile(session_id))


@router.get("/sessions/{session_id}/profile")
def profile(session_id: str) -> dict:
    ensure_session(session_id)
    return ensure_profile(session_id)


@router.patch("/sessions/{session_id}/profile")
def update_profile(session_id: str, patch: dict) -> dict:
    ensure_session(session_id)
    return merge_profile_patch(session_id, patch)
