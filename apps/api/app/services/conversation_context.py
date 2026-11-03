from __future__ import annotations

import re
from typing import Any

from ..db import decode_json, encode_json, execute, now_iso, one
from .shopping_intent import EPHEMERAL, LASTING, _budget

DEVICE_RE = re.compile(r"\b(ps5|playstation 5|xbox|switch|macbook|iphone|tv)\b|电脑|笔记本|显示器|电视", re.I)
REFRESH_RE = re.compile(r"4k\s*@?\s*120|120\s*hz|4k\s*120", re.I)
LENGTH_RE = re.compile(r"(\d+)\s*(ft|feet|foot|m|meter)s?\b", re.I)
MONITOR_RE = re.compile(r"\bmonitor\b|显示器", re.I)
HDMI_RE = re.compile(r"\bhdmi\b|hdmi", re.I)
HDMI_ARC_RE = re.compile(r"hdmi[\s\-]*arc", re.I)
SOUNDBAR_RE = re.compile(r"\bsoundbar\b", re.I)
SPEAKER_RE = re.compile(r"\bspeakers?\b", re.I)
DVI_RE = re.compile(r"\bdvi\b|dvi", re.I)
WIRED_AUDIO_RE = re.compile(r"\b(?:simple\s+)?wired\s+(?:audio\s+)?(?:connection|input|speakers?)\b|\b3\.5\s*mm\b|\baux(?:iliary)?\s*(?:in|input)?\b", re.I)
USE_CASE_RE = re.compile(r"\b(movies?|everyday tv|music|dialogue|dialog|gaming)\b", re.I)
EXCEPTION_RE = re.compile(r"\b(this time|for this|high-end pair|not my usual|exception)\b", re.I)
IMAGE_QUALITY_RE = re.compile(r"image quality|picture quality|display quality", re.I)


def blank_context() -> dict[str, Any]:
    return {
        "devices": [],
        "requirements": [],
        "future_plans": [],
        "use_cases": [],
        "shown_product_ids": [],
        "listed_product_ids": [],
        "pending_clarification": None,
        "session_budget_max": None,
        "session_budget_ephemeral": False,
        "category_hint": None,
        "focus_product_ids": [],
        "rejected_product_ids": [],
        "rejection_reasons": {},
        "task_exception": None,
        "behavior_signals": {"cheaper_requests": 0, "compatibility_checks": 0},
        "current_priority_override": None,
    }


def load_context(conversation_id: str, session_id: str) -> dict[str, Any]:
    row = one("SELECT context_json FROM conversation_context WHERE conversation_id=?", (conversation_id,))
    if not row:
        return blank_context()
    data = decode_json(row["context_json"], {})
    return {**blank_context(), **data} if isinstance(data, dict) else blank_context()


def save_context(conversation_id: str, session_id: str, context: dict[str, Any]) -> None:
    ts = now_iso()
    execute(
        "INSERT INTO conversation_context(conversation_id, session_id, context_json, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET context_json=excluded.context_json, updated_at=excluded.updated_at",
        (conversation_id, session_id, encode_json(context), ts),
    )


def update_from_message(context: dict[str, Any], message: str, product_id: str | None, action: str) -> dict[str, Any]:
    text = (message or "").strip()
    next_ctx = {**blank_context(), **context}
    if product_id:
        ids = list(dict.fromkeys([product_id, *(next_ctx.get("focus_product_ids") or [])]))[:6]
        next_ctx["focus_product_ids"] = ids
    for match in DEVICE_RE.finditer(text):
        raw_device = match.group(1) or match.group(0)
        device = raw_device.upper().replace("PLAYSTATION 5", "PS5")
        devices = list(next_ctx.get("devices") or [])
        if device not in devices:
            devices.append(device)
        next_ctx["devices"] = devices[:6]
    if REFRESH_RE.search(text):
        reqs = list(next_ctx.get("requirements") or [])
        if "4K@120Hz" not in reqs:
            reqs.append("4K@120Hz")
        next_ctx["requirements"] = reqs
    if re.search(r"4k.{0,8}60|60\s*hz", text, re.I) and not REFRESH_RE.search(text):
        reqs = list(next_ctx.get("requirements") or [])
        if "4K@60Hz" not in reqs:
            reqs.append("4K@60Hz")
        next_ctx["requirements"] = reqs
    if re.search(r"only need 1080|1080p", text, re.I):
        reqs = list(next_ctx.get("requirements") or [])
        if "1080p" not in reqs:
            reqs.append("1080p")
        next_ctx["requirements"] = reqs
    length = LENGTH_RE.search(text)
    if length:
        reqs = list(next_ctx.get("requirements") or [])
        label = f"At least {length.group(1)} {length.group(2)}"
        if label not in reqs:
            reqs.append(label)
        next_ctx["requirements"] = reqs
    if HDMI_ARC_RE.search(text):
        reqs = list(next_ctx.get("requirements") or [])
        if "HDMI ARC" not in reqs:
            reqs.append("HDMI ARC")
        next_ctx["requirements"] = reqs
    if WIRED_AUDIO_RE.search(text):
        reqs = list(next_ctx.get("requirements") or [])
        if "Wired audio input" not in reqs:
            reqs.append("Wired audio input")
        next_ctx["requirements"] = reqs
    if SOUNDBAR_RE.search(text):
        next_ctx["category_hint"] = "soundbar"
    elif DVI_RE.search(text):
        next_ctx["category_hint"] = "dvi"
        reqs = list(next_ctx.get("requirements") or [])
        if "HDMI-to-DVI" not in reqs:
            reqs.append("HDMI-to-DVI")
        next_ctx["requirements"] = reqs
    elif SPEAKER_RE.search(text):
        next_ctx["category_hint"] = "speaker"
    elif HDMI_RE.search(text) and next_ctx.get("category_hint") not in {"soundbar", "speaker", "monitor", "dvi"}:
        next_ctx["category_hint"] = "hdmi"
    if MONITOR_RE.search(text) and not SOUNDBAR_RE.search(text) and next_ctx.get("category_hint") != "soundbar":
        next_ctx["category_hint"] = "monitor"
    for match in USE_CASE_RE.finditer(text):
        label = match.group(1).lower()
        if label in {"dialog", "dialogue"}:
            label = "dialogue"
        if label == "movies":
            label = "movies"
        cases = list(next_ctx.get("use_cases") or [])
        if label not in cases:
            cases.append(label)
        next_ctx["use_cases"] = cases[:6]
    budget = _budget(text)
    if budget is not None:
        next_ctx["session_budget_max"] = budget
        next_ctx["session_budget_ephemeral"] = bool(EPHEMERAL.search(text) or not LASTING.search(text))
    if EXCEPTION_RE.search(text):
        next_ctx["task_exception"] = text[:240]
    if IMAGE_QUALITY_RE.search(text):
        next_ctx["current_priority_override"] = "image_quality_over_price"
    next_ctx = _apply_decision_switch(next_ctx, text)
    signals = dict(next_ctx.get("behavior_signals") or {})
    if action == "cheaper" or re.search(r"cheaper|overpay|don't want to overpay|更便宜|便宜一点|价格低", text, re.I):
        signals["cheaper_requests"] = int(signals.get("cheaper_requests") or 0) + 1
    if re.search(r"compatible|compatibility|work with|兼容|适配", text, re.I):
        signals["compatibility_checks"] = int(signals.get("compatibility_checks") or 0) + 1
    next_ctx["behavior_signals"] = signals
    return next_ctx


def _apply_decision_switch(context: dict[str, Any], text: str) -> dict[str, Any]:
    reqs = list(context.get("requirements") or [])

    def _drop(label: str) -> None:
        while label in reqs:
            reqs.remove(label)

    if re.search(r"planning a 120\s*hz upgrade|planning.{0,24}120\s*hz|(?:准备|计划|升级).{0,12}120\s*hz", text, re.I):
        _drop("4K@60Hz")
        if "4K@120Hz" not in reqs:
            reqs.append("4K@120Hz")
        context["requirements"] = reqs
        context["current_priority_override"] = "refresh_120"
        context["goal"] = None
    elif re.search(r"staying at 60\s*hz|stay at 60|(?:继续|只|仍然).{0,10}(?:使用|留在|选择)?\s*60\s*hz", text, re.I):
        _drop("4K@120Hz")
        if "4K@60Hz" not in reqs:
            reqs.append("4K@60Hz")
        context["requirements"] = reqs
        context["current_priority_override"] = "refresh_60"
        context["goal"] = "find_cheaper"
    elif re.search(r"prioritize lower price|keep (the )?price (down|low)|优先.{0,8}(?:降低价格|更便宜|低价)", text, re.I):
        context["current_priority_override"] = "find_cheaper"
        context["goal"] = "find_cheaper"
    return context


def context_for_api(context: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "devices": context.get("devices") or [],
        "requirements": context.get("requirements") or [],
        "future_plans": context.get("future_plans") or [],
        "use_cases": context.get("use_cases") or [],
        "session_budget_max": context.get("session_budget_max"),
        "session_budget_ephemeral": context.get("session_budget_ephemeral"),
        "category_hint": context.get("category_hint"),
        "focus_product_ids": context.get("focus_product_ids") or [],
        "current_priority_override": context.get("current_priority_override"),
        "task_exception": context.get("task_exception"),
    }
