from __future__ import annotations

from typing import Any

from ..db import decode_json, encode_json, execute, now_iso, one
from .conversation_context import load_context, save_context


def hydrate_turn_log_from_client_state(conversation_id: str, session_id: str) -> dict[str, Any]:
    row = one(
        "SELECT state_json FROM picki_conversations WHERE id=? AND session_id=?",
        (conversation_id, session_id),
    )
    context = load_context(conversation_id, session_id)
    if not row:
        return context
    state = decode_json(row.get("state_json"), {})
    messages = state.get("messages") if isinstance(state, dict) else []
    log = []
    for message in messages or []:
        if not isinstance(message, dict) or not str(message.get("text") or "").strip():
            continue
        role = "user" if message.get("from") == "you" else "assistant"
        log.append({"role": role, "text": str(message["text"])[:800]})
    context["turn_log"] = log[-20:]
    product_id = state.get("productId") if isinstance(state, dict) else None
    if product_id:
        context["anchor_product_id"] = product_id
        context.setdefault("focused_product_id", product_id)
        context["focus_product_ids"] = list(dict.fromkeys([product_id, *(context.get("focus_product_ids") or [])]))[:6]
    save_context(conversation_id, session_id, context)
    return context


def mirror_turn_log_to_picki_conversation(conversation_id: str, session_id: str) -> dict[str, Any]:
    context = load_context(conversation_id, session_id)
    existing = one(
        "SELECT title, state_json, created_at FROM picki_conversations WHERE id=? AND session_id=?",
        (conversation_id, session_id),
    )
    state = decode_json(existing.get("state_json") if existing else None, {})
    if not isinstance(state, dict):
        state = {}
    messages = []
    for index, turn in enumerate(context.get("turn_log") or []):
        if not isinstance(turn, dict) or not str(turn.get("text") or "").strip():
            continue
        role = turn.get("role")
        messages.append({
            "id": f"{'you' if role == 'user' else 'picki'}-{index}",
            "from": "you" if role == "user" else "picki",
            "text": str(turn["text"]),
        })
    product_id = context.get("focused_product_id") or context.get("anchor_product_id")
    state.update({"messages": messages, "productId": product_id})
    ts = now_iso()
    execute(
        "INSERT OR REPLACE INTO picki_conversations(id,session_id,title,state_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (
            conversation_id,
            session_id,
            (existing or {}).get("title") or "Shopping chat",
            encode_json(state),
            (existing or {}).get("created_at") or ts,
            ts,
        ),
    )
    return state
