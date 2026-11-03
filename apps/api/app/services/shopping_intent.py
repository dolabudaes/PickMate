from __future__ import annotations

import re
from typing import Any

STYLE_TERMS = {
    "minimal": ["compact", "slim", "minimal", "clean", "simple", "sleek"],
    "bold": ["rgb", "party", "colorful", "bold"],
    "value": ["value", "budget"],
}

STYLE_LABELS = {
    "minimal": "You like clean, minimal designs",
    "bold": "You like bolder designs",
    "value": "You look for good value",
}

EPHEMERAL = re.compile(
    r"only for today|just for today|just today|this time only|only this once|temporary budget|not my usual|for now only",
    re.I,
)
LASTING = re.compile(r"\b(usually|always|in general|my style|i tend to|from now on|for future purchases|remember that)\b", re.I)
TASTE = re.compile(r"\b(i like|i love|i prefer|i'm into|i am into)\b", re.I)
GIFT = re.compile(r"\b(gift|present|for a friend|for my friend|for my (mom|dad|mother|father|wife|husband|partner|sister|brother|kid))\b|送礼|送朋友", re.I)
CHEAPER = re.compile(r"\b(cheaper|less expensive|lower price|more affordable|too expensive|too pricey)\b|贵了|便宜一点|再便宜", re.I)
DIFFERENT = re.compile(r"different vibe|another style|different style|different look|换个风格|另一种风格", re.I)
WHY = re.compile(r"why this|why is this|why that one|为什么是这个|为什么选", re.I)
COMPARE = re.compile(r"\bcompare\b|对比|比较一下", re.I)
MINIMAL = re.compile(r"minimal|clean look|cleaner look|clean design|simple design|sleek", re.I)
BOLD = re.compile(r"\bbold\b|colorful|statement piece|rgb", re.I)
VALUE = re.compile(r"good value|bang for the buck|性价比", re.I)
RECIPIENT_TASTE = re.compile(r"\b(they|she|he) likes?\b", re.I)


def blank_session() -> dict[str, Any]:
    return {
        "query": "speaker",
        "budget_max": None,
        "budget_ephemeral": False,
        "style": None,
        "recipient": "self",
        "current_product_id": None,
        "alternative_ids": [],
        "rejected_product_ids": [],
        "memory_mentioned": False,
        "goal": "",
    }


def interpret(message: str, action: str, session: dict[str, Any]) -> dict[str, Any]:
    text = (message or "").strip()
    lower_action = action or "message"
    update = {
        "rerank": "none",
        "explain": None,
        "budget": None,
        "budget_ephemeral": bool(EPHEMERAL.search(text)),
        "style": None,
        "style_is_lasting": False,
        "style_scope": "personal",
        "recipient": None,
        "query": None,
        "focus_product_id": None,
    }
    if GIFT.search(text):
        update["recipient"] = "gift"
    if update["budget_ephemeral"]:
        update["budget"] = _budget(text)
    elif _budget(text) is not None:
        update["budget"] = _budget(text)
    style = _style(text)
    if style and not RECIPIENT_TASTE.search(text):
        update["style"] = style
        update["style_is_lasting"] = bool(LASTING.search(text) or TASTE.search(text)) and not update["budget_ephemeral"]
        if update["budget_ephemeral"]:
            update["style_is_lasting"] = False
    elif style and RECIPIENT_TASTE.search(text):
        update["style"] = style
        update["style_scope"] = "recipient"
        update["style_is_lasting"] = False
    if LASTING.search(text) and update["budget"] is not None and not update["budget_ephemeral"]:
        update["lasting_budget"] = update["budget"]
    else:
        update["lasting_budget"] = None

    category = _category(text)
    if category:
        update["query"] = category
    elif re.search(r"surprise me", text, re.I):
        update["query"] = session.get("query") or "speaker"

    if lower_action == "cheaper" or (lower_action == "message" and CHEAPER.search(text)):
        update["rerank"] = "cheaper"
    elif lower_action == "different_style" or (lower_action == "message" and DIFFERENT.search(text)):
        update["rerank"] = "style"
    elif lower_action == "why_this" or (lower_action == "message" and WHY.search(text) and not category):
        update["explain"] = "why"
    elif lower_action == "compare" or (lower_action == "message" and COMPARE.search(text) and not category):
        update["explain"] = "compare"
    elif lower_action == "focus":
        update["rerank"] = "focus"
    elif lower_action == "promote":
        update["rerank"] = "promote"
    elif category or update["budget"] is not None or update["style"] or update["recipient"] == "gift" or _new_goal(text) or not session.get("current_product_id"):
        if text or category or update["budget"] is not None:
            update["rerank"] = "fresh"
    elif text and session.get("current_product_id"):
        update["explain"] = "why"

    if update["style"] and update["rerank"] == "fresh":
        update["rerank"] = "fresh"
    if update["rerank"] == "cheaper" and update["style"]:
        update["rerank"] = "cheaper"
    return update


def apply_update(session: dict[str, Any], update: dict[str, Any], focus_product_id: str | None = None) -> dict[str, Any]:
    next_session = {**blank_session(), **session}
    if update.get("query"):
        next_session["query"] = update["query"]
    if update.get("budget") is not None:
        next_session["budget_max"] = update["budget"]
        next_session["budget_ephemeral"] = bool(update.get("budget_ephemeral"))
    if update.get("style") and update.get("style_scope") != "recipient":
        next_session["style"] = update["style"]
    elif update.get("style") and update.get("style_scope") == "recipient":
        next_session["style"] = update["style"]
        next_session["recipient"] = "gift"
    if update.get("recipient") == "gift":
        next_session["recipient"] = "gift"
    if focus_product_id and update.get("rerank") in {"focus", "promote"}:
        next_session["current_product_id"] = focus_product_id
    return next_session


def retrieval_plan(session: dict[str, Any], update: dict[str, Any], memories: list[dict[str, Any]]) -> dict[str, Any]:
    query = session.get("query") or "speaker"
    budget = session.get("budget_max")
    exclude = list(session.get("rejected_product_ids") or [])
    current = session.get("current_product_id")
    rerank = update.get("rerank")
    apply_personal = session.get("recipient") != "gift"
    style = session.get("style") if apply_personal or update.get("style_scope") == "recipient" else None
    if not apply_personal and update.get("style_scope") != "recipient":
        style = None
    prefer = list(STYLE_TERMS.get(style or "", []))
    if apply_personal:
        for memory in memories:
            if not memory.get("enabled", 1) or memory.get("scope") != "personal":
                continue
            prefer.extend(STYLE_TERMS.get(memory.get("value"), []))
            if memory.get("facet") == "note":
                prefer.extend(re.findall(r"[a-z]{4,}", str(memory.get("label") or "").lower())[:4])
    prefer = list(dict.fromkeys(term for term in prefer if term))
    max_price = float(budget) if budget is not None else None
    if max_price is None and apply_personal:
        for memory in memories:
            if not memory.get("enabled", 1) or memory.get("scope") != "personal" or memory.get("facet") != "budget":
                continue
            try:
                max_price = float(memory.get("value"))
            except (TypeError, ValueError):
                continue
            break
    if rerank == "cheaper" and current:
        exclude.append(current)
    if rerank == "style" and current:
        exclude.append(current)
        if not style:
            prefer = ["compact", "slim"]
    if rerank == "focus" and current:
        exclude.append(current)
    message = f"Find a {query}"
    if prefer and (rerank in {"style", "fresh", "cheaper", "focus"} or style):
        message += " " + " ".join(prefer[:3])
    if max_price is not None:
        message += f" under ${int(max_price)}"
    if rerank == "cheaper" and max_price is not None:
        message += " cheaper"
    return {
        "message": message.strip(),
        "max_price": max_price,
        "exclude_product_ids": list(dict.fromkeys(exclude)),
        "prefer_terms": prefer if apply_personal or update.get("style_scope") == "recipient" or rerank == "style" else [],
        "apply_personal": apply_personal,
    }


def cheaper_ceiling(current_price: float | None, budget: float | None) -> float | None:
    if current_price is None or current_price <= 0:
        return budget
    ceiling = current_price - 0.01
    if budget is not None:
        ceiling = min(ceiling, budget)
    return ceiling if ceiling > 0 else None


def compose_reply(
    *,
    kind: str,
    saved_amount: float | None = None,
    tradeoff: str | None = None,
    why: str | None = None,
    caution: str | None = None,
    remembered_label: str | None = None,
    cleaner: bool = False,
) -> str:
    if kind == "empty":
        return "I couldn’t find a real catalog match for that. Try a speaker, soundbar, or a budget and I’ll look again."
    if kind == "kept":
        return "I looked through the catalog, and nothing cheaper still fits. I’ll keep this one."
    if kind == "style_kept":
        return "I couldn’t find a different look that still fits. This stays the pick."
    if kind == "why":
        reason = why or "It matches the budget and catalog facts I can check."
        note = caution or "Check the current price on Amazon before you buy."
        return f"{reason} One trade-off: {note}"
    if kind == "compare":
        return why or "I only have one solid match right now. Ask for a cheaper option or a different vibe."
    if kind == "cheaper" and saved_amount and saved_amount > 0:
        save = _money(saved_amount)
        look = " and has a cleaner look" if cleaner else ""
        give = f" You do give up {tradeoff}." if tradeoff else " I don’t see a catalog fact that shows a clear downside."
        return f"Got you! This one saves you {save}{look} 🧡{give}"
    if kind == "style":
        give = f" You do give up {tradeoff}." if tradeoff else ""
        return f"Here’s a different option, and I kept your budget.{give}"
    if kind == "focus":
        return "This is the one you opened. Want a cheaper similar option or a different vibe?"
    if kind == "remembered":
        phrase = remembered_label or "clean designs"
        return f"I remembered you like {phrase}. Here’s where I’d start ✨"
    if kind == "first_open":
        return "Ooh, I have one in mind! ✨ Want it cheaper or a different vibe?"
    return "Ooh, I have one in mind! ✨ This is my favorite match for your budget. Want it cheaper or a different vibe?"


def why_for_you(product: dict[str, Any], budget: float | None, style: str | None) -> str:
    price = _price(product)
    parts: list[str] = []
    if budget is not None and price is not None and price <= budget:
        parts.append(f"It fits a {_money(budget)} budget")
    elif price is not None:
        parts.append(f"Catalog price is {_money(price)}")
    rating = product.get("rating") or 0
    reviews = int(product.get("reviewCount") or 0)
    if rating and reviews:
        parts.append(f"rated {float(rating):.1f} from {reviews} reviews")
    if style == "minimal" and _style_hits(product, "minimal"):
        parts.append("the listing text leans compact and simple")
    if not parts:
        return "This is the strongest catalog match I can support."
    sentence = parts[0]
    if len(parts) > 1:
        sentence = f"{parts[0]}, and it is {parts[1]}" if parts[1].startswith("rated") else f"{parts[0]}, and {parts[1]}"
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def one_caution(product: dict[str, Any]) -> str:
    themes = [str(item).strip() for item in product.get("negativeThemes") or [] if str(item).strip()]
    if themes:
        text = themes[0]
        text = re.sub(r"^Product feature:\s*", "", text, flags=re.I)
        return text[:140]
    reviews = int(product.get("reviewCount") or 0)
    if 0 < reviews < 20:
        return f"Only {reviews} reviews in the catalog, so the rating is thin."
    if _price(product) is None:
        return "This row has no catalog price, so I can’t confirm it fits a budget."
    return "Catalog price is a reference, not a live Amazon deal."


def evidenced_tradeoff(previous: dict[str, Any] | None, current: dict[str, Any]) -> str | None:
    if not previous:
        return None
    notes: list[str] = []
    prev_reviews = int(previous.get("reviewCount") or 0)
    next_reviews = int(current.get("reviewCount") or 0)
    prev_rating = float(previous.get("rating") or 0)
    next_rating = float(current.get("rating") or 0)
    if prev_reviews >= 20 and next_reviews >= 20 and prev_rating - next_rating >= 0.3:
        notes.append(f"a {prev_rating:.1f} rating for a {next_rating:.1f}")
    elif prev_reviews > next_reviews * 2 and prev_reviews >= 50:
        notes.append("a larger review count")
    prev_features = _features(previous)
    next_text = _blob(current)
    for feature in prev_features:
        token = feature.lower()
        if len(token) >= 12 and token not in next_text:
            notes.append(feature[:80])
            break
    return notes[0] if notes else None


def price_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> float | None:
    before = _price(previous) if previous else None
    after = _price(current)
    if before is None or after is None or after >= before:
        return None
    return round(before - after, 2)


def looks_cleaner(previous: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if not previous:
        return False
    return _style_hits(current, "minimal") > _style_hits(previous, "minimal")


def amazon_url(product: dict[str, Any]) -> str | None:
    details = (product.get("sourceFields") or {}).get("details") or {}
    for key, value in details.items() if isinstance(details, dict) else []:
        if str(key).lower() in {"url", "amazon_url", "product_url"} and _http(value):
            return str(value)
    product_id = str(product.get("id") or "")
    if re.fullmatch(r"[A-Z0-9]{10}", product_id):
        return f"https://www.amazon.com/dp/{product_id}"
    return None


def reference_price(product: dict[str, Any]) -> float | None:
    source = (product.get("sourceFields") or {}).get("price")
    if source is None:
        return None
    try:
        amount = float(source)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def card(product: dict[str, Any], budget: float | None, style: str | None) -> dict[str, Any]:
    price = reference_price(product)
    return {
        "product": product,
        "product_id": product.get("id"),
        "why_for_you": why_for_you(product, budget, style),
        "one_caution": one_caution(product),
        "reference_price": price,
        "price_label": "Catalog reference price" if price is not None else None,
        "price_verified_at": product.get("dataUpdatedAt"),
        "amazon_url": amazon_url(product),
    }


def memory_candidate(update: dict[str, Any]) -> dict[str, str] | None:
    if update.get("lasting_budget") is not None:
        amount = update["lasting_budget"]
        return {
            "facet": "budget",
            "value": str(int(amount)),
            "label": f"You usually shop under {_money(float(amount))}",
            "scope": "personal",
        }
    style = update.get("style")
    if style and update.get("style_is_lasting") and update.get("style_scope") == "personal":
        return {
            "facet": "style",
            "value": style,
            "label": STYLE_LABELS.get(style, style),
            "scope": "personal",
        }
    return None


def _budget(text: str) -> float | None:
    match = re.search(r"(?:under|below|less than|around|about|budget|[$¥￥])\s*[$¥￥]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if not match:
        match = re.search(r"[$¥￥]\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def _style(text: str) -> str | None:
    if MINIMAL.search(text):
        return "minimal"
    if BOLD.search(text):
        return "bold"
    if VALUE.search(text):
        return "value"
    return None


def _new_goal(text: str) -> bool:
    return bool(re.search(r"\b(find|want|need|looking|shop|surprise|upgrade|get me)\b|帮我找|想买", text, re.I))


def _category(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"sound ?bars?", lower):
        return "soundbar"
    if re.search(r"home theaters?|movie night|surround", lower):
        return "soundbar"
    if re.search(r"speakers?", lower):
        return "speaker"
    if re.search(r"receivers?", lower):
        return "receiver"
    return None


def _price(product: dict[str, Any] | None) -> float | None:
    if not product:
        return None
    return reference_price(product)


def _features(product: dict[str, Any]) -> list[str]:
    source = product.get("sourceFields") or {}
    values = source.get("features") or []
    return [str(item).strip() for item in values if str(item).strip()]


def _blob(product: dict[str, Any]) -> str:
    source = product.get("sourceFields") or {}
    parts = [product.get("name") or "", product.get("description") or "", *(_features(product)), *(source.get("description") or [])]
    return " ".join(str(part) for part in parts).lower()


def _style_hits(product: dict[str, Any], style: str) -> int:
    text = _blob(product)
    return sum(1 for term in STYLE_TERMS.get(style, []) if term in text)


def _money(amount: float) -> str:
    if abs(amount - round(amount)) < 0.001:
        return f"${amount:.0f}"
    return f"${amount:.2f}"


def _http(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("https://")
