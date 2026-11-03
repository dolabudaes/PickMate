from __future__ import annotations

from typing import Any

from .taste_consolidator import list_taste, taste_use_in_recommendations
from .taste_schema import STATUS_ACTIVE, STATUS_DISMISSED, STATUS_SUGGESTED


def retrieve_for_task(
    session_id: str,
    *,
    category_hint: str | None,
    message: str,
    session_context: dict[str, Any],
) -> dict[str, Any]:
    if not taste_use_in_recommendations(session_id):
        return {"global": [], "category_specific": [], "session_constraints": _session_constraints(session_context), "priority_labels": []}

    items = [item for item in list_taste(session_id) if item.get("enabled")]
    explicit = []
    inferred = []
    for item in items:
        if item.get("status") == STATUS_DISMISSED:
            continue
        if item.get("source_type") == "explicit" or item.get("user_confirmed"):
            explicit.append(item)
        # Inferred preferences remain visible suggestions until the user confirms them.
        # Confidence alone must never turn a guess into a ranking rule.
        elif item.get("status") == STATUS_ACTIVE and item.get("user_confirmed"):
            inferred.append(item)

    global_prefs = []
    category_prefs = []
    hint = (category_hint or "").lower()
    for item in explicit + inferred:
        pc = (item.get("product_category") or "").lower()
        if pc and hint and pc == hint:
            category_prefs.append(item)
        elif not pc or item.get("scope") == "personal":
            global_prefs.append(item)

    global_prefs = _dedupe(global_prefs)[:4]
    category_prefs = _dedupe(category_prefs)[:3]
    priority = _priority_labels(session_context, explicit, inferred)
    return {
        "global": global_prefs,
        "category_specific": category_prefs,
        "session_constraints": _session_constraints(session_context),
        "priority_labels": priority,
    }


def _session_constraints(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "devices": context.get("devices") or [],
        "requirements": context.get("requirements") or [],
        "budget_max": context.get("session_budget_max"),
        "budget_ephemeral": context.get("session_budget_ephemeral"),
        "priority_override": context.get("current_priority_override"),
        "task_exception": context.get("task_exception"),
    }


def _priority_labels(context: dict[str, Any], explicit: list[dict[str, Any]], inferred: list[dict[str, Any]]) -> list[str]:
    if context.get("current_priority_override") == "image_quality_over_price":
        return ["Image quality for this purchase", *_labels_from_prefs(explicit, inferred)[:2]]
    session = _session_constraints(context)
    labels = []
    for req in session.get("requirements") or []:
        labels.append(req)
    for device in session.get("devices") or []:
        labels.append(f"Works with {device}")
    labels.extend(_labels_from_prefs(explicit, inferred))
    return list(dict.fromkeys(labels))[:6]


def _labels_from_prefs(explicit: list[dict[str, Any]], inferred: list[dict[str, Any]]) -> list[str]:
    out = []
    for item in explicit:
        out.append(item.get("normalized_preference") or item.get("label") or "")
    for item in inferred:
        if float(item.get("confidence") or 0) >= 0.75:
            out.append(item.get("normalized_preference") or item.get("label") or "")
    return [label for label in out if label]


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for item in items:
        key = str(item.get("normalized_preference") or item.get("label"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def personalization_profile(retrieved: dict[str, Any]) -> str:
    labels = retrieved.get("priority_labels") or []
    if not labels:
        return "balanced"
    for raw in labels:
        label = str(raw).lower()
        if "compatibility" in label or "兼容" in label or "适配" in label:
            return "compatibility_first"
        if "value" in label or "budget" in label or "性价比" in label or "价格" in label:
            return "value_first"
        if "image quality" in label or "画质" in label:
            return "quality_first"
    return "balanced"
