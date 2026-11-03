from __future__ import annotations

import os
import secrets
from typing import Any

from ..db import decode_json, encode_json, execute, now_iso, one, query
from .taste_schema import STATUS_ACTIVE, STATUS_DISMISSED, STATUS_SUGGESTED, STATUS_SUPERSEDED, taste_row_to_api

INFERRED_CONFIDENCE_THRESHOLD = 0.72


def apply_operations(session_id: str, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not taste_learning_enabled(session_id):
        return []
    saved_events: list[dict[str, Any]] = []
    for operation in operations:
        op = operation.get("op")
        if op == "ADD":
            event = _add(session_id, operation)
            if event:
                saved_events.append(event)
        elif op == "REINFORCE":
            _reinforce(session_id, operation)
        elif op == "REFINE":
            _refine(session_id, operation)
        elif op == "SUPERSEDE":
            _supersede(session_id, operation)
        elif op == "DISMISS":
            _dismiss(session_id, operation)
    return saved_events


def taste_learning_enabled(session_id: str) -> bool:
    if os.getenv("PICKI_TASTE_LEARNING_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    row = one("SELECT taste_learning_enabled, memory_enabled FROM shopping_settings WHERE session_id=?", (session_id,))
    if not row:
        return True
    if row.get("memory_enabled") == 0:
        return False
    return row.get("taste_learning_enabled", 1) != 0


def taste_use_in_recommendations(session_id: str) -> bool:
    row = one("SELECT taste_use_in_recommendations, memory_enabled FROM shopping_settings WHERE session_id=?", (session_id,))
    if not row:
        return True
    if row.get("memory_enabled") == 0:
        return False
    return row.get("taste_use_in_recommendations", 1) != 0


def _add(session_id: str, operation: dict[str, Any]) -> dict[str, Any] | None:
    record = operation.get("record") or {}
    source_type = operation.get("source_type") or record.get("source_type") or "explicit"
    facet = record.get("facet") or "note"
    value = record.get("value") or record.get("normalized") or "preference"
    normalized = record.get("normalized") or record.get("label") or value
    category = record.get("category") or "general"
    product_category = record.get("product_category")

    if _dismissed_match(session_id, facet, value, normalized, category):
        return None
    existing = _find_duplicate(session_id, facet, value, normalized, category, product_category)
    if existing:
        _reinforce(session_id, {
            "match": {"id": existing["id"]},
            "confidence_delta": 0.08 if source_type == "explicit" else 0.05,
            "evidence": record.get("original_user_expression"),
            "evidence_message_ids": record.get("evidence_message_ids") or [],
        })
        if source_type == "explicit":
            execute(
                "UPDATE preference_memories SET user_confirmed=1, source_type='explicit', status=?, label=?, normalized_preference=?, updated_at=? WHERE id=?",
                (STATUS_ACTIVE, _display_label(normalized), normalized, now_iso(), existing["id"]),
            )
        return {"id": existing["id"], "label": _display_label(normalized), "saved": False, "reinforced": True, "source_type": source_type}

    if source_type == "inferred" and float(record.get("confidence") or 0) < INFERRED_CONFIDENCE_THRESHOLD:
        status = STATUS_SUGGESTED
        user_confirmed = 0
    else:
        status = STATUS_ACTIVE if source_type == "explicit" else STATUS_SUGGESTED
        user_confirmed = 1 if source_type == "explicit" else 0

    memory_id = f"mem-{secrets.token_hex(6)}"
    ts = now_iso()
    label = _display_label(normalized)
    execute(
        "INSERT INTO preference_memories("
        "id, session_id, facet, value, label, scope, confidence, evidence, source, enabled, created_at, updated_at, "
        "category, normalized_preference, source_type, status, user_confirmed, original_user_expression, "
        "evidence_message_ids, supporting_evidence_count, first_observed_at, product_category"
        ") VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            memory_id,
            session_id,
            facet,
            value,
            label,
            record.get("scope") or "personal",
            float(record.get("confidence") or (0.9 if source_type == "explicit" else 0.6)),
            (record.get("original_user_expression") or "")[:280],
            "explicit" if source_type == "explicit" else "inferred",
            ts,
            ts,
            category,
            normalized,
            source_type,
            status,
            user_confirmed,
            record.get("original_user_expression"),
            encode_json(record.get("evidence_message_ids") or []),
            1,
            ts,
            product_category,
        ),
    )
    return {"id": memory_id, "label": label, "saved": True, "reinforced": False, "source_type": source_type}


def _reinforce(session_id: str, operation: dict[str, Any]) -> None:
    match = operation.get("match") or {}
    row = None
    if match.get("id"):
        row = one("SELECT * FROM preference_memories WHERE session_id=? AND id=?", (session_id, match["id"]))
    elif match.get("facet") and match.get("value"):
        row = one(
            "SELECT * FROM preference_memories WHERE session_id=? AND facet=? AND value=? AND status!=?",
            (session_id, match["facet"], match["value"], STATUS_DISMISSED),
        )
    if not row:
        return
    evidence_ids = decode_json(row.get("evidence_message_ids"), [])
    for item in operation.get("evidence_message_ids") or []:
        if item not in evidence_ids:
            evidence_ids.append(item)
    count = int(row.get("supporting_evidence_count") or 1) + 1
    confidence = min(float(row.get("confidence") or 0.5) + float(operation.get("confidence_delta") or 0.05), 0.95)
    status = row.get("status")
    if status == STATUS_SUGGESTED and confidence >= INFERRED_CONFIDENCE_THRESHOLD:
        status = STATUS_ACTIVE
    execute(
        "UPDATE preference_memories SET confidence=?, supporting_evidence_count=?, evidence_message_ids=?, updated_at=?, status=? WHERE id=?",
        (confidence, count, encode_json(evidence_ids[-12:]), now_iso(), status, row["id"]),
    )


def _refine(session_id: str, operation: dict[str, Any]) -> None:
    pref_id = operation.get("preference_id")
    if not pref_id:
        return
    execute(
        "UPDATE preference_memories SET label=?, normalized_preference=?, original_user_expression=?, user_confirmed=1, updated_at=? WHERE session_id=? AND id=?",
        (operation.get("label"), operation.get("normalized_preference"), operation.get("original_user_expression"), now_iso(), session_id, pref_id),
    )


def _supersede(session_id: str, operation: dict[str, Any]) -> None:
    old_id = operation.get("preference_id")
    new_id = operation.get("superseded_by")
    if not old_id:
        return
    execute(
        "UPDATE preference_memories SET status=?, superseded_by=?, enabled=0, updated_at=? WHERE session_id=? AND id=?",
        (STATUS_SUPERSEDED, new_id, now_iso(), session_id, old_id),
    )


def _dismiss(session_id: str, operation: dict[str, Any]) -> None:
    pref_id = operation.get("preference_id")
    if not pref_id:
        return
    execute(
        "UPDATE preference_memories SET status=?, enabled=0, dismissed_at=?, updated_at=? WHERE session_id=? AND id=?",
        (STATUS_DISMISSED, now_iso(), now_iso(), session_id, pref_id),
    )


def _dismissed_match(session_id: str, facet: str, value: str, normalized: str, category: str) -> bool:
    row = one(
        "SELECT id FROM preference_memories WHERE session_id=? AND status=? AND (normalized_preference=? OR (facet=? AND value=?))",
        (session_id, STATUS_DISMISSED, normalized, facet, value),
    )
    return bool(row)


def _find_duplicate(session_id: str, facet: str, value: str, normalized: str, category: str, product_category: str | None) -> dict[str, Any] | None:
    row = one(
        "SELECT * FROM preference_memories WHERE session_id=? AND facet=? AND value=? AND status NOT IN (?, ?)",
        (session_id, facet, value, STATUS_DISMISSED, STATUS_SUPERSEDED),
    )
    if row:
        return row
    rows = query(
        "SELECT * FROM preference_memories WHERE session_id=? AND normalized_preference=? AND category=? AND status NOT IN (?, ?)",
        (session_id, normalized, category, STATUS_DISMISSED, STATUS_SUPERSEDED),
    )
    for item in rows:
        if product_category and item.get("product_category") and item.get("product_category") != product_category:
            continue
        return item
    return None


def _display_label(normalized: str) -> str:
    mapping = {
        "Compatibility first": "Compatibility first",
        "Good value": "Good value",
        "Brand isn't a priority": "Brand isn't a priority",
        "Value over brand prestige": "Value over brand prestige",
        "Clean, minimal designs": "Clean, minimal designs",
        "Image quality over price": "Image quality over price",
    }
    return mapping.get(normalized, normalized)


def list_taste(session_id: str) -> list[dict[str, Any]]:
    rows = query(
        "SELECT * FROM preference_memories WHERE session_id=? AND status NOT IN (?, ?) ORDER BY priority DESC, updated_at DESC",
        (session_id, STATUS_SUPERSEDED, STATUS_DISMISSED),
    )
    return [taste_row_to_api(row) for row in rows]


def patch_taste(session_id: str, preference_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = one("SELECT * FROM preference_memories WHERE session_id=? AND id=?", (session_id, preference_id))
    if not row:
        return None
    label = patch.get("normalized_preference") or patch.get("label") or row.get("label")
    status = patch.get("status") or row.get("status")
    user_confirmed = 1 if patch.get("user_confirmed", True) else 0
    enabled = 0 if status == STATUS_DISMISSED else 1
    facet = row.get("facet")
    value = row.get("value")
    normalized = label
    if patch.get("label") or patch.get("normalized_preference"):
        from .taste_extractor import extract_from_turn
        extracted = extract_from_turn(str(label), "message", "", {})
        record = ((extracted.get("operations") or [{}])[0]).get("record") or {}
        if record.get("facet"):
            facet = record.get("facet")
            value = record.get("value") or value
            normalized = record.get("normalized") or label
    display = normalized
    expression = str(patch.get("label") or row.get("original_user_expression") or label)
    priority = int(patch.get("priority") if patch.get("priority") is not None else (row.get("priority") or 50))
    execute(
        "UPDATE preference_memories SET label=?, normalized_preference=?, original_user_expression=?, facet=?, value=?, status=?, user_confirmed=?, enabled=?, priority=?, updated_at=? WHERE id=? AND session_id=?",
        (display, normalized, expression[:280], facet, value, status, user_confirmed, enabled, priority, now_iso(), preference_id, session_id),
    )
    updated = one("SELECT * FROM preference_memories WHERE id=?", (preference_id,))
    return taste_row_to_api(updated) if updated else None


def delete_taste(session_id: str, preference_id: str) -> bool:
    row = one("SELECT id FROM preference_memories WHERE session_id=? AND id=?", (session_id, preference_id))
    if not row:
        return False
    execute(
        "UPDATE preference_memories SET status=?, enabled=0, dismissed_at=?, updated_at=? WHERE id=? AND session_id=?",
        (STATUS_DISMISSED, now_iso(), now_iso(), preference_id, session_id),
    )
    return True
