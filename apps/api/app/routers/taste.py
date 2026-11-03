from __future__ import annotations

from fastapi import APIRouter, Query

from ..schemas import TastePatchIn
from ..services.conversation_context import context_for_api, load_context
from ..services.taste_consolidator import delete_taste, list_taste, patch_taste

router = APIRouter()


@router.get("/my-taste")
def my_taste(session_id: str = Query(...)) -> dict:
    return {"items": list_taste(session_id)}


@router.patch("/my-taste/{preference_id}")
def update_taste(preference_id: str, body: TastePatchIn) -> dict:
    updated = patch_taste(body.session_id, preference_id, body.model_dump(exclude={"session_id"}, exclude_none=True))
    if not updated:
        return {"status": "not_found"}
    return updated


@router.delete("/my-taste/{preference_id}")
def remove_taste(preference_id: str, session_id: str = Query(...)) -> dict:
    ok = delete_taste(session_id, preference_id)
    return {"status": "removed" if ok else "not_found", "id": preference_id}


@router.get("/picki/conversations/{conversation_id}/context")
def conversation_context(conversation_id: str, session_id: str = Query(...)) -> dict:
    context = load_context(conversation_id, session_id)
    return context_for_api(context, conversation_id)
