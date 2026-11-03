from __future__ import annotations

from typing import Any

from ..db import db, decode_json, encode_json, execute, now_iso, query

TASTE_CATEGORIES = (
    "price_value",
    "style",
    "quality",
    "performance",
    "compatibility",
    "brand",
    "features",
    "shopping_habits",
    "general",
)

STATUS_ACTIVE = "active"
STATUS_SUGGESTED = "suggested"
STATUS_DISMISSED = "dismissed"
STATUS_SUPERSEDED = "superseded"

MIGRATION_COLUMNS = {
    "category": "TEXT NOT NULL DEFAULT 'general'",
    "normalized_preference": "TEXT",
    "source_type": "TEXT NOT NULL DEFAULT 'explicit'",
    "status": "TEXT NOT NULL DEFAULT 'active'",
    "user_confirmed": "INTEGER NOT NULL DEFAULT 0",
    "original_user_expression": "TEXT",
    "evidence_message_ids": "TEXT NOT NULL DEFAULT '[]'",
    "supporting_evidence_count": "INTEGER NOT NULL DEFAULT 1",
    "first_observed_at": "TEXT",
    "dismissed_at": "TEXT",
    "superseded_by": "TEXT",
    "product_category": "TEXT",
    "priority": "INTEGER NOT NULL DEFAULT 50",
}


def migrate_taste_schema() -> None:
    with db() as conn:
        rows = conn.execute("PRAGMA table_info(preference_memories)").fetchall()
        existing = {row[1] for row in rows}
        for name, ddl in MIGRATION_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE preference_memories ADD COLUMN {name} {ddl}")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS conversation_context (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                context_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        settings = conn.execute("PRAGMA table_info(shopping_settings)").fetchall()
        setting_cols = {row[1] for row in settings}
        if "taste_learning_enabled" not in setting_cols:
            conn.execute("ALTER TABLE shopping_settings ADD COLUMN taste_learning_enabled INTEGER NOT NULL DEFAULT 1")
        if "taste_use_in_recommendations" not in setting_cols:
            conn.execute("ALTER TABLE shopping_settings ADD COLUMN taste_use_in_recommendations INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    _backfill_normalized()


def _backfill_normalized() -> None:
    rows = query("SELECT id, label, facet, value, source, created_at FROM preference_memories WHERE normalized_preference IS NULL OR normalized_preference = ''")
    for row in rows:
        label = row["label"]
        source_type = "explicit" if row.get("source") == "explicit" else "inferred"
        category = _facet_to_category(row.get("facet") or "note")
        execute(
            "UPDATE preference_memories SET normalized_preference=?, category=?, source_type=?, first_observed_at=?, user_confirmed=? WHERE id=?",
            (label, category, source_type, row.get("created_at") or now_iso(), 1 if source_type == "explicit" else 0, row["id"]),
        )


def _facet_to_category(facet: str) -> str:
    return {
        "budget": "price_value",
        "style": "style",
        "note": "general",
        "compatibility": "compatibility",
        "value": "price_value",
        "brand": "brand",
        "quality": "quality",
    }.get(facet, "general")


def taste_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    source_type = row.get("source_type") or ("explicit" if row.get("source") == "explicit" else "inferred")
    status = row.get("status") or (STATUS_ACTIVE if row.get("enabled", 1) else STATUS_DISMISSED)
    return {
        "id": row["id"],
        "user_id": row["session_id"],
        "normalized_preference": row.get("normalized_preference") or row.get("label"),
        "label": row.get("label"),
        "category": row.get("category") or _facet_to_category(row.get("facet") or "note"),
        "scope": row.get("scope") or "personal",
        "source_type": source_type,
        "confidence": float(row.get("confidence") or 0.5),
        "evidence_message_ids": decode_json(row.get("evidence_message_ids"), []),
        "supporting_evidence_count": int(row.get("supporting_evidence_count") or 1),
        "first_observed_at": row.get("first_observed_at") or row.get("created_at"),
        "last_updated_at": row.get("updated_at"),
        "status": status,
        "user_confirmed": bool(row.get("user_confirmed")) or source_type == "explicit",
        "original_user_expression": row.get("original_user_expression") or row.get("evidence"),
        "enabled": bool(row.get("enabled", 1)) and status not in {STATUS_DISMISSED, STATUS_SUPERSEDED},
        "facet": row.get("facet"),
        "value": row.get("value"),
        "priority": int(50 if row.get("priority") is None else row.get("priority")),
    }
