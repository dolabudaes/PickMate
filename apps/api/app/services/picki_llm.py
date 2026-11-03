from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .product_relevance import (
    DISPLAY_MONITOR,
    GENERIC_AUDIO,
    HDMI_CABLE,
    HEADPHONES,
    PRODUCT_FOCUS,
    SPEAKER,
    SOUNDBAR,
    UNKNOWN,
    ShoppingIntent,
    detect_shopping_intent,
)


def llm_configured() -> bool:
    api_key = os.getenv("PICKI_MODEL_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = (os.getenv("PICKI_MODEL_BASE_URL") or os.getenv("LLM_BASE_URL") or "").rstrip("/")
    return bool(api_key and base_url and os.getenv("LLM_MODE", "mock") == "real")


def model_config() -> dict[str, Any]:
    api_key = os.getenv("PICKI_MODEL_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = (os.getenv("PICKI_MODEL_BASE_URL") or os.getenv("LLM_BASE_URL") or "").rstrip("/")
    model = os.getenv("PICKI_MODEL_NAME") or os.getenv("LLM_MODEL", "gpt-4.1-mini")
    return {"api_key": api_key, "base_url": base_url, "model": model}

_INTENT_KINDS = {
    DISPLAY_MONITOR,
    HDMI_CABLE,
    HEADPHONES,
    SPEAKER,
    SOUNDBAR,
    GENERIC_AUDIO,
    PRODUCT_FOCUS,
    UNKNOWN,
}


async def resolve_shopping_intent(
    message: str,
    *,
    product_id: str | None,
    session_context: dict[str, Any] | None,
    use_llm: bool,
) -> ShoppingIntent:
    rule_intent = detect_shopping_intent(message, product_id=product_id, session_context=session_context)
    if not use_llm or rule_intent.kind not in {UNKNOWN, GENERIC_AUDIO}:
        return rule_intent
    llm_intent = await infer_shopping_intent(message, product_id=product_id, session_context=session_context)
    if llm_intent and llm_intent.kind != UNKNOWN:
        return llm_intent
    return rule_intent


async def infer_shopping_intent(
    message: str,
    *,
    product_id: str | None,
    session_context: dict[str, Any] | None,
) -> ShoppingIntent | None:
    if not llm_configured():
        return None
    ctx = session_context or {}
    hint = ctx.get("category_hint") or ""
    system = (
        "You classify shopping intent for a home-audio and accessories catalog. "
        "Return JSON only: {\"kind\": string, \"query\": string|null}. "
        f"kind must be one of: {', '.join(sorted(_INTENT_KINDS))}. "
        "Use display_monitor for computer/gaming monitors (not studio monitor headphones). "
        "Use hdmi_cable for HDMI cables. Use product_focus when user refers to a product already in context."
    )
    user = json.dumps(
        {
            "message": message,
            "product_id": product_id,
            "category_hint": hint,
        },
        ensure_ascii=False,
    )
    data = await _chat_completion(system, user, json_mode=True, timeout=18)
    if not data:
        return None
    return parse_intent_payload(data)


def parse_intent_payload(payload: dict[str, Any]) -> ShoppingIntent | None:
    kind = (payload.get("kind") or "").strip().lower()
    if kind not in _INTENT_KINDS:
        return None
    query = payload.get("query")
    if query is not None and not isinstance(query, str):
        query = str(query)
    reject = "studio_monitor_headphones" if kind == DISPLAY_MONITOR else None
    return ShoppingIntent(kind, query=query or None, reject_reason=reject)


async def polish_primary_message(
    *,
    user_message: str,
    draft_message: str,
    key_facts: list[str],
    response_mode: str,
    product: dict[str, Any] | None,
) -> str | None:
    if not llm_configured() or not (draft_message or "").strip():
        return None
    facts = [str(f) for f in (key_facts or [])[:6]]
    product_line = ""
    if product:
        title = product.get("title") or product.get("name") or ""
        price = product.get("reference_price")
        price_bit = f" Catalog price ${float(price):.2f}." if price is not None else ""
        product_line = f"Product: {title}.{price_bit}"
    system = (
        "You are Picki, a concise shopping assistant. Rewrite the draft reply for the user. "
        "Rules: use only facts from draft and key_facts; do not invent specs, prices, or stock; "
        "keep the same language as the user message; "
        f"mode {response_mode}: QUICK ≤80 words, STANDARD ≤140, DEEP ≤220; "
        "no markdown headings or bullet lists in the main message; friendly and direct."
    )
    user = json.dumps(
        {
            "user_message": user_message,
            "draft_message": draft_message,
            "key_facts": facts,
            "product": product_line,
        },
        ensure_ascii=False,
    )
    text = await _chat_completion_text(system, user, timeout=22)
    if not text:
        return None
    cleaned = text.strip().strip('"')
    if len(cleaned) < 8:
        return None
    return cleaned


async def chat_json(system: str, user: str, timeout: float = 20) -> dict[str, Any] | None:
    return await _chat_completion(system, user, json_mode=True, timeout=timeout)


async def _chat_completion(system: str, user: str, *, json_mode: bool, timeout: float) -> dict[str, Any] | None:
    content = await _raw_chat(system, user, json_mode=json_mode, timeout=timeout)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


async def _chat_completion_text(system: str, user: str, timeout: float) -> str | None:
    return await _raw_chat(system, user, json_mode=False, timeout=timeout)


async def _raw_chat(system: str, user: str, *, json_mode: bool, timeout: float) -> str | None:
    cfg = model_config()
    if not cfg["api_key"] or not cfg["base_url"]:
        return None
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"authorization": f"Bearer {cfg['api_key']}", "content-type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{cfg['base_url']}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content")
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return None
