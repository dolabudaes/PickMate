from __future__ import annotations

from typing import Any

from .conversation_context import context_for_api, load_context, save_context, update_from_message
from .taste_consolidator import apply_operations
from .taste_extractor import extract_from_turn
from .taste_retriever import retrieve_for_task


def process_turn(
    session_id: str,
    conversation_id: str,
    message: str,
    action: str,
    product_id: str | None,
) -> dict[str, Any]:
    context = load_context(conversation_id, session_id)
    context = update_from_message(context, message, product_id, action)
    save_context(conversation_id, session_id, context)

    extraction = extract_from_turn(message, action, conversation_id, context)
    taste_events = apply_operations(session_id, extraction.get("operations") or [])

    taste_saved = None
    updated_events = [
        item for item in taste_events
        if item.get("saved") or (item.get("reinforced") and item.get("source_type") == "explicit")
    ]
    if updated_events:
        labels = [str(item.get("label") or "") for item in updated_events if item.get("label")]
        taste_saved = {
            "ids": [str(item.get("id")) for item in updated_events if item.get("id")],
            "id": updated_events[0].get("id"),
            "labels": labels,
            "label": ", ".join(labels),
            "undoable": True,
            "source_type": updated_events[0].get("source_type", "explicit"),
        }
        taste_saved["acknowledgement"] = _acknowledgement(labels[0] if len(labels) == 1 else taste_saved["label"])

    retrieved = retrieve_for_task(
        session_id,
        category_hint=context.get("category_hint"),
        message=message,
        session_context=context,
    )
    return {
        "conversation_context": context_for_api(context, conversation_id),
        "taste_saved": taste_saved,
        "retrieved_taste": retrieved,
        "taste_acknowledgement": taste_saved.get("acknowledgement") if taste_saved else None,
    }


def _acknowledgement(label: str) -> str:
    mapping = {
        "Compatibility first": "I'll prioritize compatibility first, then price, when comparing products for you.",
        "Good value": "I'll prioritize value when comparing suitable products.",
        "Brand isn't a priority": "I'll treat brand as a soft preference, not a requirement.",
        "Value over brand prestige": "I'll prioritize value over brand when comparing suitable products.",
    }
    return mapping.get(label, f"I'll keep this in mind: {label}.")
