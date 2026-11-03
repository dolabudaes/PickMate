from __future__ import annotations

import secrets

from fastapi import APIRouter

from fastapi import HTTPException

from ..db import db, decode_json, encode_json, execute, now_iso, one, query
from ..schemas import DecisionIn
from ..services.events import ensure_session
from ..services.profile import ensure_profile, save_profile

router = APIRouter()


@router.post("/decisions")
def save_decision(body: DecisionIn) -> dict:
    ensure_session(body.session_id)
    decision_id = f"decision-{secrets.token_hex(8)}"
    ts = now_iso()
    execute(
        "INSERT INTO saved_decisions(id,session_id,user_need,result_json,created_at) VALUES(?,?,?,?,?)",
        (decision_id, body.session_id, body.user_need, encode_json(body.result), ts),
    )
    record_decision_history(body.session_id, body.result)
    return {"id": decision_id, "sessionId": body.session_id, "createdAt": ts, "userNeed": body.user_need, "result": body.result}


@router.get("/sessions/{session_id}/decisions")
def decisions(session_id: str) -> list[dict]:
    rows = query("SELECT * FROM saved_decisions WHERE session_id=? ORDER BY created_at DESC", (session_id,))
    return [{"id": r["id"], "createdAt": r["created_at"], "userNeed": r["user_need"], "result": decode_json(r["result_json"], {})} for r in rows]


@router.put("/sessions/{session_id}/decision-state")
def save_decision_state(session_id: str, body: dict) -> dict:
    ensure_session(session_id)
    ts = now_iso()
    execute(
        "INSERT OR REPLACE INTO decision_sessions(id,session_id,state_json,updated_at) VALUES(?,?,?,?)",
        (session_id, session_id, encode_json(body), ts),
    )
    return {"sessionId": session_id, "updatedAt": ts, "state": body}


@router.get("/sessions/{session_id}/decision-state")
def get_decision_state(session_id: str) -> dict:
    ensure_session(session_id)
    row = one("SELECT state_json, updated_at FROM decision_sessions WHERE session_id=?", (session_id,))
    if not row:
        raise HTTPException(404, "No resumable decision session")
    return {"sessionId": session_id, "updatedAt": row["updated_at"], "state": decode_json(row["state_json"], {})}


@router.get("/sessions/{session_id}/conversations")
def list_conversations(session_id: str) -> list[dict]:
    ensure_session(session_id)
    rows = query(
        "SELECT id, title, state_json, created_at, updated_at FROM picki_conversations WHERE session_id=? ORDER BY updated_at DESC",
        (session_id,),
    )
    items = []
    for row in rows:
        state = decode_json(row.get("state_json"), {})
        if state.get("archivedAt"):
            continue
        items.append({
            "id": row["id"],
            "title": row["title"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "manualTitle": bool(state.get("manualTitle")),
        })
    return items


@router.post("/sessions/{session_id}/conversations")
def create_conversation(session_id: str, body: dict) -> dict:
    ensure_session(session_id)
    conversation_id = body.get("id") or f"chat-{secrets.token_hex(8)}"
    ts = now_iso()
    title = str(body.get("title") or "New conversation")[:80]
    state = body.get("state") or {}
    execute(
        "INSERT OR REPLACE INTO picki_conversations(id,session_id,title,state_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (conversation_id, session_id, title, encode_json(state), ts, ts),
    )
    return {"id": conversation_id, "title": title, "createdAt": ts, "updatedAt": ts, "state": state}


@router.put("/sessions/{session_id}/conversations/{conversation_id}")
def update_conversation(session_id: str, conversation_id: str, body: dict) -> dict:
    ensure_session(session_id)
    existing = one("SELECT * FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
    # A delayed client autosave must not recreate a conversation the user has
    # already deleted. Creation has its own POST endpoint and a fresh ID.
    if not existing:
        raise HTTPException(404, "Conversation not found")
    ts = now_iso()
    existing_state = decode_json(existing.get("state_json"), {})
    manual_title = bool(existing_state.get("manualTitle"))
    title = str((existing.get("title") if existing and manual_title else body.get("title")) or "New conversation")[:80]
    state = {**(body.get("state") or {}), "manualTitle": manual_title}
    # Archival is server-owned metadata. A delayed client autosave may replace
    # the editable conversation state, but it must not make an archived demo
    # record visible again.
    for key in ("archivedAt", "archivedBy", "archiveFixtureVersion"):
        if key in existing_state:
            state[key] = existing_state[key]
    created = existing["created_at"]
    updated = execute(
        "UPDATE picki_conversations SET title=?, state_json=?, updated_at=? WHERE id=? AND session_id=?",
        (title, encode_json(state), ts, conversation_id, session_id),
    )
    if updated.rowcount != 1:
        raise HTTPException(404, "Conversation not found")
    return {"id": conversation_id, "title": title, "createdAt": created, "updatedAt": ts, "state": state}


@router.patch("/sessions/{session_id}/conversations/{conversation_id}")
def patch_conversation(session_id: str, conversation_id: str, body: dict) -> dict:
    ensure_session(session_id)
    existing = one("SELECT * FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
    if not existing:
        raise HTTPException(404, "Conversation not found")
    title = str(body.get("title") or existing["title"] or "New conversation").strip()[:80] or "New conversation"
    state = decode_json(existing["state_json"], {})
    if "title" in body:
        state["manualTitle"] = True
    if isinstance(body.get("state"), dict):
        state = {**state, **body["state"]}
    ts = now_iso()
    execute(
        "UPDATE picki_conversations SET title=?, state_json=?, updated_at=? WHERE id=? AND session_id=?",
        (title, encode_json(state), ts, conversation_id, session_id),
    )
    return {"id": conversation_id, "title": title, "createdAt": existing["created_at"], "updatedAt": ts, "state": state}


@router.delete("/sessions/{session_id}/conversations/{conversation_id}")
def delete_conversation(session_id: str, conversation_id: str) -> dict:
    ensure_session(session_id)
    existing = one("SELECT id FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
    if not existing:
        raise HTTPException(404, "Conversation not found")
    with db() as conn:
        conn.execute("DELETE FROM shopping_sessions WHERE conversation_id=? AND session_id=?", (conversation_id, session_id))
        conn.execute("DELETE FROM conversation_context WHERE conversation_id=? AND session_id=?", (conversation_id, session_id))
        conn.execute("DELETE FROM conversation_products WHERE conversation_id=? AND session_id=?", (conversation_id, session_id))
        conn.execute("UPDATE cart_item_provenance SET conversation_id=NULL WHERE conversation_id=?", (conversation_id,))
        conn.execute("UPDATE saved_picks SET conversation_id=NULL WHERE conversation_id=? AND session_id=?", (conversation_id, session_id))
        conn.execute("UPDATE comparisons SET conversation_id=NULL WHERE conversation_id=? AND session_id=?", (conversation_id, session_id))
        conn.execute("DELETE FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
        conn.commit()
    return {"deleted": True, "id": conversation_id}


@router.get("/sessions/{session_id}/conversations/{conversation_id}")
def get_conversation(session_id: str, conversation_id: str) -> dict:
    ensure_session(session_id)
    row = one("SELECT * FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
    if not row:
        raise HTTPException(404, "Conversation not found")
    return {
        "id": row["id"],
        "title": row["title"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "state": decode_json(row["state_json"], {}),
    }


def record_decision_history(session_id: str, result: dict) -> None:
    primary = result.get("primaryRecommendation") or result.get("primary")
    product = (primary or {}).get("product") or {}
    product_id = product.get("id")
    if not product_id:
        return
    profile = ensure_profile(session_id)
    history = profile.setdefault("decision_history", {"view": [], "compare": [], "save": [], "choose": [], "reject": []})
    for bucket in ("save", "choose"):
        values = history.setdefault(bucket, [])
        if product_id not in values:
            values.append(product_id)
    save_profile(session_id, profile)
