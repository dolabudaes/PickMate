from __future__ import annotations

import secrets
from typing import Any

from ..db import encode_json, execute, now_iso, query


def create_session() -> str:
    session_id = f"session-{secrets.token_hex(10)}"
    ts = now_iso()
    execute("INSERT INTO sessions(id,created_at,updated_at) VALUES(?,?,?)", (session_id, ts, ts))
    return session_id


def ensure_session(session_id: str) -> str:
    execute(
        "INSERT OR IGNORE INTO sessions(id,created_at,updated_at) VALUES(?,?,?)",
        (session_id, now_iso(), now_iso()),
    )
    return session_id


def record_event(session_id: str, name: str, product_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_session(session_id)
    event_id = f"event-{secrets.token_hex(8)}"
    ts = now_iso()
    execute(
        "INSERT INTO browsing_events(id,session_id,name,product_id,metadata,created_at) VALUES(?,?,?,?,?,?)",
        (event_id, session_id, name, product_id, encode_json(metadata or {}), ts),
    )
    execute("UPDATE sessions SET updated_at=? WHERE id=?", (ts, session_id))
    if product_id:
        update_profile_history(session_id, name, product_id)
    return {"id": event_id, "sessionId": session_id, "name": name, "productId": product_id, "createdAt": ts}


def session_events(session_id: str) -> list[dict[str, Any]]:
    return query("SELECT * FROM browsing_events WHERE session_id=? ORDER BY created_at ASC", (session_id,))


def update_profile_history(session_id: str, name: str, product_id: str) -> None:
    bucket = {
        "product_viewed": "view",
        "primary_recommendation_viewed": "view",
        "alternative_viewed": "view",
        "product_added_to_compare": "compare",
        "product_removed_from_compare": "reject",
        "add_to_cart_after_picki": "choose",
        "purchase_intent_after_picki": "choose",
    }.get(name)
    if not bucket:
        return
    from .profile import ensure_profile, save_profile

    profile = ensure_profile(session_id)
    history = profile.setdefault("decision_history", {"view": [], "compare": [], "save": [], "choose": [], "reject": []})
    values = history.setdefault(bucket, [])
    if product_id not in values:
        values.append(product_id)
    save_profile(session_id, profile)
