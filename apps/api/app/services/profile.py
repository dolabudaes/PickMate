from __future__ import annotations

from typing import Any

from ..db import decode_json, encode_json, execute, now_iso, one
from ..schemas import SessionProfile


def default_profile() -> dict[str, Any]:
    return SessionProfile().model_dump()


def ensure_profile(session_id: str) -> dict[str, Any]:
    row = one("SELECT profile_json FROM decision_profiles WHERE session_id=?", (session_id,))
    if row:
        return normalize_profile(decode_json(row["profile_json"], default_profile()))
    profile = default_profile()
    execute(
        "INSERT INTO decision_profiles(session_id,profile_json,updated_at) VALUES(?,?,?)",
        (session_id, encode_json(profile), now_iso()),
    )
    return profile


def save_profile(session_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    execute(
        "INSERT OR REPLACE INTO decision_profiles(session_id,profile_json,updated_at) VALUES(?,?,?)",
        (session_id, encode_json(profile), now_iso()),
    )
    return profile


def merge_profile_patch(session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    profile = ensure_profile(session_id)
    for key, value in patch.items():
        if key == "priorities" and isinstance(value, dict):
            profile["priorities"] = {**profile.get("priorities", {}), **value}
        elif key == "budget" and isinstance(value, dict):
            profile["budget"] = {**profile.get("budget", {}), **value}
        else:
            profile[key] = value
    return save_profile(session_id, profile)


def upsert_preference(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    profile = ensure_profile(session_id)
    preference = str(payload["preference"])
    ts = now_iso()
    preferences = profile.setdefault("preferences", [])
    existing = next((item for item in preferences if item.get("id") == preference or item.get("preference") == preference), None)
    entry = {
        "id": existing.get("id", preference) if existing else preference,
        "preference": preference,
        "value": payload.get("value") if payload.get("value") is not None else payload.get("weight"),
        "weight": payload.get("weight"),
        "source": payload.get("source", "explicit"),
        "confidence": clamp(float(payload.get("confidence", 0.9)), 0.0, 1.0),
        "scope": payload.get("scope", "long_term"),
        "category": payload.get("category"),
        "created_at": existing.get("created_at", ts) if existing else ts,
        "updated_at": ts,
    }
    if existing:
        preferences[preferences.index(existing)] = entry
    else:
        preferences.append(entry)
    apply_preference_to_profile(profile, entry)
    return save_profile(session_id, profile)


def delete_preference(session_id: str, preference_id: str) -> dict[str, Any]:
    profile = ensure_profile(session_id)
    profile["preferences"] = [
        item
        for item in profile.get("preferences", [])
        if item.get("id") != preference_id and item.get("preference") != preference_id
    ]
    profile.get("priorities", {}).pop(preference_id, None)
    category_preferences = profile.get("category_preferences", {})
    for values in category_preferences.values():
        values.pop(preference_id, None)
    if preference_id == "device_platform":
        profile["device_platform"] = "any"
    if preference_id == "budget_max":
        profile["budget"] = {**profile.get("budget", {}), "max": None}
    if preference_id == "shopping_style":
        profile["shopping_style"] = []
    profile["observed_signals"] = [
        item for item in profile.get("observed_signals", []) if item.get("preference") != preference_id
    ]
    return save_profile(session_id, profile)


def apply_preference_update(profile: dict[str, Any], text: str) -> tuple[dict[str, Any], bool, str]:
    next_profile = {**profile, "priorities": {**profile.get("priorities", {})}}
    changed = False
    messages: list[str] = []
    if any(k in text.lower() for k in ["电话", "会议", "通话", "开会", "phone meeting", "conference call", "calls every day", "many phone"]):
        next_profile["priorities"]["call_quality"] = 0.95
        next_profile.setdefault("explicit_concerns", [])
        if "call_quality" not in next_profile["explicit_concerns"]:
            next_profile["explicit_concerns"].append("call_quality")
        changed = True
        messages.append("Raised call/meeting priority for this session")
    if any(k in text for k in ["舒适", "戴久", "耳朵疼", "不胀"]):
        next_profile["priorities"]["comfort"] = 0.95
        next_profile["small_ear_friendly"] = True
        changed = True
        messages.append("Raised comfort priority for this session")
    if any(k in text for k in ["降噪", "安静", "地铁太吵"]):
        next_profile["priorities"]["noise_cancellation"] = 0.96
        changed = True
        messages.append("Raised noise-cancellation priority for this session")
    if any(k in text for k in ["便宜", "性价比", "省钱", "价格"]):
        next_profile["priorities"]["price_value"] = 0.92
        next_profile["budget_preference"] = "strict"
        changed = True
        messages.append("Raised price/value priority for this session")
    if any(k in text for k in ["质量", "品质", "评分", "口碑", "好评", "review", "rating", "quality"]):
        next_profile["priorities"]["quality"] = 0.9
        next_profile["priorities"]["review_confidence"] = 0.82
        next_profile["budget_preference"] = "quality_first"
        changed = True
        messages.append("Raised quality/review-evidence priority for this session")
    if any(k in text for k in ["耐用", "耐久", "结实", "durable", "durability", "sturdy"]):
        next_profile["priorities"]["durability"] = 0.86
        next_profile["risk_preference"] = "risk_averse"
        changed = True
        messages.append("Raised durability priority for this session")
    import re
    match = re.search(r"(\d{3,4})\s*元?(以内|以下|内|预算)?", text)
    if match:
        next_profile["budget"] = {**next_profile.get("budget", {}), "max": int(match.group(1))}
        changed = True
        messages.append("Updated this session budget")
    return next_profile, changed, ", ".join(messages) if messages else "No preference change recognized"


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    base = default_profile()
    merged = {**base, **profile}
    merged["budget"] = {**base.get("budget", {}), **profile.get("budget", {})}
    merged["priorities"] = {**base.get("priorities", {}), **profile.get("priorities", {})}
    merged["preferences"] = list(profile.get("preferences", []))
    merged["observed_signals"] = list(profile.get("observed_signals", []))
    merged["decision_history"] = {
        **base.get("decision_history", {}),
        **profile.get("decision_history", {}),
    }
    merged["category_preferences"] = {
        **base.get("category_preferences", {}),
        **profile.get("category_preferences", {}),
    }
    merged["shopping_style"] = list(profile.get("shopping_style", base.get("shopping_style", [])))
    return merged


def apply_preference_to_profile(profile: dict[str, Any], entry: dict[str, Any]) -> None:
    preference = entry["preference"]
    weight = entry.get("weight")
    scope = entry.get("scope")
    if scope == "observed":
        signals = profile.setdefault("observed_signals", [])
        signals[:] = [item for item in signals if item.get("preference") != preference]
        signals.append(entry)
        return
    if scope == "category" and entry.get("category"):
        category = profile.setdefault("category_preferences", {}).setdefault(entry["category"], {})
        if isinstance(weight, (int, float)):
            category[preference] = float(weight)
        return
    if preference == "device_platform" and entry.get("value") in {"android", "ios", "any"}:
        profile["device_platform"] = entry["value"]
        return
    if preference == "budget_max" and isinstance(entry.get("value"), (int, float)):
        profile["budget"] = {**profile.get("budget", {}), "max": int(entry["value"])}
        return
    if preference == "budget_preference" and entry.get("value") in {"strict", "flexible", "quality_first", "unknown"}:
        profile["budget_preference"] = entry["value"]
        return
    if preference == "risk_preference" and entry.get("value") in {"risk_averse", "balanced", "risk_tolerant", "unknown"}:
        profile["risk_preference"] = entry["value"]
        return
    if preference == "shopping_style" and isinstance(entry.get("value"), str):
        styles = profile.setdefault("shopping_style", [])
        if entry["value"] not in styles:
            styles.append(entry["value"])
        return
    if isinstance(weight, (int, float)):
        profile.setdefault("priorities", {})[preference] = float(weight)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
