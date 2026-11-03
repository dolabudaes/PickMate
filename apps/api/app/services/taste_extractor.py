from __future__ import annotations

import re
from typing import Any

from .shopping_intent import EPHEMERAL, LASTING, TASTE

EXPLICIT_RULES: list[tuple[re.Pattern[str], dict[str, str]]] = [
    (re.compile(r"(?:以后|今后|长期).{0,24}(?:兼容性|适配).{0,24}(?:价格|便宜)|(?:兼容性|适配).{0,16}(?:比|优先于).{0,16}(?:最低价格|便宜)", re.I), {"category": "compatibility", "normalized": "兼容性优先", "facet": "compatibility", "value": "compatibility_first", "lasting": "1"}),
    (re.compile(r"fits? my setup.{0,48}(?:cheapest|lowest price)", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first", "lasting": "1"}),
    (re.compile(r"compatibility.*(?:than|over).*(?:brand|name)", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first"}),
    (re.compile(r"(?:care|prioriti[sz]e).*(?:compatibility|compatible).*(?:than|over).*(?:brand|name)", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first"}),
    (re.compile(r"(?:value|price).*(?:than|over).*(?:brand|prestige|name)", re.I), {"category": "price_value", "normalized": "Good value", "facet": "value", "value": "value_over_brand"}),
    (re.compile(r"brand.*(?:isn't|is not|not).*(?:priority|important)", re.I), {"category": "brand", "normalized": "Brand isn't a priority", "facet": "brand", "value": "brand_low_priority"}),
    (re.compile(r"(?:compatibility|compatible).*(?:first|matter)", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first"}),
    (re.compile(r"(?:pay|spend)(?:ing)? (?:a little|slightly) more.{0,48}(?:genuinely|actually|clearly) better", re.I), {"category": "price_value", "normalized": "Worth the extra cost", "facet": "value", "value": "meaningful_premium"}),
    (re.compile(r"(?:hate|avoid|don'?t like).{0,32}(?:paying|spending).{0,32}features? (?:i|we) won'?t use", re.I), {"category": "features", "normalized": "Avoid unused features", "facet": "features", "value": "avoid_unused_features"}),
    (re.compile(r"(?:good\s+value|value\s+(?:over|than)|don't want to overpay|bang for the buck)", re.I), {"category": "price_value", "normalized": "Good value", "facet": "value", "value": "good_value"}),
    (re.compile(r"(?:care|prioriti[sz]e).+(?:than|over)\s+brand(?:\s+names?)?\b", re.I), {"category": "brand", "normalized": "Brand isn't a priority", "facet": "brand", "value": "brand_low_priority"}),
    (re.compile(r"minimal|clean design|simple design", re.I), {"category": "style", "normalized": "Clean, minimal designs", "facet": "style", "value": "minimal"}),
    (re.compile(r"usually prefer good value", re.I), {"category": "price_value", "normalized": "Value over brand prestige", "facet": "value", "value": "value_over_brand", "lasting": "1"}),
    (re.compile(r"usually shop under \$?(\d+)", re.I), {"category": "price_value", "normalized": "Usually under budget cap", "facet": "budget", "value": "budget_cap"}),
    (re.compile(r"image quality.*(?:than|over).*price", re.I), {"category": "performance", "normalized": "Image quality over price", "facet": "quality", "value": "image_quality"}),
    (re.compile(r"compatibility matters more.{0,40}(lowest )?price|care more about compatibility.{0,40}(lowest )?price", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first", "lasting": "1"}),
    (re.compile(r"(lowest )?price.{0,24}matters more.{0,24}compatib|(care more about|prioriti[sz]e).{0,16}(price|value|saving)", re.I), {"category": "price_value", "normalized": "Good value", "facet": "value", "value": "good_value", "lasting": "1"}),
    (re.compile(r"remember that i care more about compatibility", re.I), {"category": "compatibility", "normalized": "Compatibility first", "facet": "compatibility", "value": "compatibility_first", "lasting": "1"}),
]

HYPOTHETICAL = re.compile(r"\b(what if|would it|could it|should i|if i)\b|如果|假如", re.I)


def extract_from_turn(
    message: str,
    action: str,
    conversation_id: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    text = (message or "").strip()
    operations: list[dict[str, Any]] = []
    chat_confirmations: list[dict[str, Any]] = []
    if not text or HYPOTHETICAL.search(text) and not TASTE.search(text):
        return {"operations": operations, "chat_confirmations": chat_confirmations}

    seen_normalized: set[str] = set()
    for pattern, meta in EXPLICIT_RULES:
        if not pattern.search(text):
            continue
        if meta["normalized"] in seen_normalized:
            continue
        seen_normalized.add(meta["normalized"])
        lasting = meta.get("lasting") == "1" or (LASTING.search(text) or TASTE.search(text)) and not EPHEMERAL.search(text)
        if meta.get("facet") == "budget" and not lasting:
            continue
        if "overpay" in text.lower() and not lasting and not re.search(r"usually|always|in general", text, re.I):
            continue
        operations.append({
            "op": "ADD",
            "source_type": "explicit",
            "user_confirmed": True,
            "record": {
                **meta,
                "scope": "personal",
                "confidence": 0.92,
                "original_user_expression": text[:280],
                "evidence_message_ids": [{"conversation_id": conversation_id, "snippet": text[:180]}],
                "product_category": context.get("category_hint"),
            },
        })
        chat_confirmations.append({"label": meta["normalized"], "source_type": "explicit"})

    signals = context.get("behavior_signals") or {}
    cheaper = int(signals.get("cheaper_requests") or 0)
    if cheaper >= 2 and not any(op.get("record", {}).get("value") == "good_value" for op in operations):
        operations.append({
            "op": "ADD",
            "source_type": "inferred",
            "user_confirmed": False,
            "record": {
                "category": "price_value",
                "normalized": "Good value",
                "facet": "value",
                "value": "good_value_inferred",
                "scope": "personal",
                "confidence": min(0.55 + cheaper * 0.08, 0.82),
                "original_user_expression": "Repeated requests for cheaper options",
                "evidence_message_ids": [{"conversation_id": conversation_id, "signal": "cheaper_requests", "count": cheaper}],
                "product_category": None,
            },
        })

    if action == "cheaper" and not operations:
        operations.append({
            "op": "REINFORCE",
            "source_type": "inferred",
            "match": {"facet": "value", "value": "good_value_inferred"},
            "confidence_delta": 0.06,
        })

    return {"operations": operations, "chat_confirmations": chat_confirmations}
