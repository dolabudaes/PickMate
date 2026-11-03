from __future__ import annotations

import re
from typing import Any

from .picki_reply import classify_reply_type, compose_natural_reply
from .product_relevance import DISPLAY_MONITOR, ShoppingIntent
from .review_provider import fetch_review_intelligence
from .shopping_compare import reference_amount
from .taste_retriever import personalization_profile

ResponseMode = str  # QUICK | STANDARD | DEEP


def pick_response_mode(message: str, action: str, session_context: dict[str, Any]) -> ResponseMode:
    text = (message or "").lower()
    if action in {"cheaper", "why_this"}:
        return "QUICK"
    if re.search(r"\b(full spec|all spec|every spec|deep dive|detailed|comprehensive)\b", text):
        return "DEEP"
    if re.search(r"\bcompare\b|versus|\bvs\.?\b|side by side", text):
        return "DEEP"
    if re.search(r"\bwhat do buyers|reviews?|customer feedback\b", text):
        return "STANDARD"
    if re.search(r"\bgood\b|\bworth\b|should i buy", text):
        return "STANDARD"
    if re.search(r"\bfind\b|\bhelp me\b|\brecommend\b|\blooking for\b", text) and len(text.split()) >= 4:
        return "QUICK"
    if len(text.split()) <= 8 and not re.search(r"\bspec|review|compare\b", text):
        return "QUICK"
    return "STANDARD"


def compose_pick_response(
    *,
    message: str,
    mode: ResponseMode,
    intent: ShoppingIntent,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    retrieved_taste: dict[str, Any],
    session_context: dict[str, Any],
    no_product_explanation: str | None = None,
    interpretation: Any | None = None,
    action: str = "message",
    action_status: dict[str, Any] | None = None,
    comparison_products: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reply_type = classify_reply_type(
        message=message,
        action=action,
        intent=intent,
        interpretation=interpretation,
        primary=primary,
        alternatives=alternatives,
        no_product_explanation=no_product_explanation,
        action_status=action_status,
    )
    composed = compose_natural_reply(
        reply_type=reply_type,
        message=message,
        intent=intent,
        primary=primary,
        alternatives=alternatives,
        retrieved_taste=retrieved_taste,
        session_context=session_context,
        interpretation=interpretation,
        no_product_explanation=no_product_explanation,
        action_status=action_status,
        comparison_products=comparison_products,
        mode=mode,
    )
    if composed.get("primary_message"):
        return composed
    profile = personalization_profile(retrieved_taste)
    if no_product_explanation:
        return _compose_no_product(mode, no_product_explanation, intent, retrieved_taste)

    if not primary:
        return _compose_no_product(mode, no_product_explanation or "Tell me what you are shopping for.", intent, retrieved_taste)

    review_intel = fetch_review_intelligence(primary)
    if mode == "QUICK":
        body = _quick_body(primary, alternatives, profile, session_context, message)
    elif mode == "DEEP":
        body = _deep_body(primary, alternatives, profile, session_context, review_intel)
    else:
        body = _standard_body(primary, alternatives, profile, session_context, review_intel, message)

    product_refs = _product_refs(primary, alternatives, message)
    detail_sections = body.pop("detail_sections", [])
    suggested_actions = _suggested_actions(message, primary, alternatives, intent)

    return {
        "response_mode": mode,
        "primary_message": body["primary_message"],
        "message": body["primary_message"],
        "key_facts": body.get("key_facts") or [],
        "product_refs": product_refs,
        "detail_sections": detail_sections,
        "suggested_actions": suggested_actions,
        "direct_recommendation": None,
        "product_highlights": [],
        "technical_specifications": [],
        "price_value_analysis": None,
        "customer_review_summary": None,
        "product_comparisons": None,
        "important_drawbacks": [],
        "suggested_follow_up_questions": [a["label"] for a in suggested_actions[:3]],
    }


def _word_trim(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(",;") + "…"


def _quick_body(
    primary: dict[str, Any],
    alternatives: list[dict[str, Any]],
    profile: str,
    session_context: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    price = reference_amount(primary)
    title = _short_title(primary)
    facts = _top_facts(primary, session_context, profile, limit=3)
    trade = _trade_line(profile, session_context)
    next_step = _next_step(message, bool(alternatives))
    parts = [f"{title}" + (f" is about ${price:.2f} in the catalog." if price else ".")]
    if facts:
        parts.append(" ".join(facts[:2]))
    if trade:
        parts.append(trade)
    parts.append(next_step)
    primary_message = _word_trim(" ".join(parts), 95)
    return {
        "primary_message": primary_message,
        "key_facts": [{"text": f} for f in facts[:3]],
        "detail_sections": _collapsed_details(primary, alternatives, include_reviews=False),
    }


def _standard_body(
    primary: dict[str, Any],
    alternatives: list[dict[str, Any]],
    profile: str,
    session_context: dict[str, Any],
    review_intel: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    price = reference_amount(primary)
    title = _short_title(primary)
    facts = _top_facts(primary, session_context, profile, limit=3)
    caveat = _caveat(primary, session_context, review_intel)
    rec = _recommendation_line(profile, session_context, caveat)
    opener = f"For your question about {title}"
    if price is not None:
        opener += f" (${price:.2f} reference price)"
    opener += f": {rec}"
    if facts:
        opener += " " + " ".join(facts[:2])
    if caveat and "review" not in message.lower():
        opener += f" Caveat: {caveat}"
    primary_message = _word_trim(opener, 145)
    sections = _collapsed_details(primary, alternatives, include_reviews="review" in message.lower())
    if "review" in message.lower() and review_intel.get("available"):
        sections.insert(0, {
            "id": "reviews",
            "title": "Review themes",
            "collapsed": True,
            "lines": _review_lines(review_intel),
        })
    return {
        "primary_message": primary_message,
        "key_facts": [{"text": f} for f in facts[:3]],
        "detail_sections": sections,
    }


def _deep_body(
    primary: dict[str, Any],
    alternatives: list[dict[str, Any]],
    profile: str,
    session_context: dict[str, Any],
    review_intel: dict[str, Any],
) -> dict[str, Any]:
    standard = _standard_body(primary, alternatives, profile, session_context, review_intel, "")
    sections = _collapsed_details(primary, alternatives, include_reviews=True, expanded=True)
    sections.extend(standard.get("detail_sections") or [])
    extra_specs = _all_specs(primary)
    if extra_specs:
        sections.append({"id": "full_specs", "title": "Complete specifications", "collapsed": False, "lines": extra_specs})
    primary_message = standard["primary_message"]
    if review_intel.get("summary"):
        primary_message += f" {review_intel['summary']}"
    return {
        "primary_message": _word_trim(primary_message, 220),
        "key_facts": standard["key_facts"],
        "detail_sections": sections,
    }


def _compose_no_product(mode: ResponseMode, text: str, intent: ShoppingIntent, retrieved_taste: dict[str, Any]) -> dict[str, Any]:
    profile = personalization_profile(retrieved_taste)
    extra = ""
    if profile == "value_first" and intent.kind == DISPLAY_MONITOR:
        extra = " When you shop monitors elsewhere, prioritize refresh rate and HDMI 2.1 for console gaming."
    elif profile == "compatibility_first":
        extra = " Match the cable or port version to your console and TV."
    message = _word_trim(text + extra, 110 if mode == "QUICK" else 150)
    actions = _suggested_actions("find", None, [], intent)
    return {
        "response_mode": mode,
        "primary_message": message,
        "message": message,
        "key_facts": [],
        "product_refs": [],
        "detail_sections": [],
        "suggested_actions": actions,
        "direct_recommendation": None,
        "product_highlights": [],
        "technical_specifications": [],
        "price_value_analysis": None,
        "customer_review_summary": None,
        "product_comparisons": None,
        "important_drawbacks": [],
        "suggested_follow_up_questions": [a["label"] for a in actions[:3]],
    }


def _short_title(product: dict[str, Any]) -> str:
    name = (product.get("name") or "").strip()
    brand = (product.get("brand") or "").strip()
    if brand and name.lower().startswith(brand.lower()):
        name = name[len(brand) :].strip(" -–—")
    return name[:72] if len(name) > 72 else name or "This product"


def _top_facts(product: dict[str, Any], session_context: dict[str, Any], profile: str, limit: int) -> list[str]:
    source = product.get("sourceFields") or {}
    features = list(source.get("features") or [])
    reqs = " ".join(session_context.get("requirements") or []).lower()
    facts: list[str] = []
    for feature in features[:6]:
        lower = feature.lower()
        if "120" in reqs and "120" in lower:
            facts.append(f"It advertises {feature}, which fits your 4K 120Hz setup.")
            continue
        if "120" in reqs and "60" in lower and "120" not in lower:
            facts.append(f"It lists {feature}, so verify 120Hz support before buying for your TV.")
            continue
        if profile == "value_first" and "hdmi" in lower:
            facts.append(f"{feature}—worth it only if you need that capability.")
            continue
        if len(feature) > 12:
            facts.append(_humanize_feature(feature))
        if len(facts) >= limit:
            break
    if not facts and features:
        facts.append(_humanize_feature(features[0]))
    price = reference_amount(product)
    if price is not None and profile == "value_first" and len(facts) < limit:
        facts.append(f"Reference price is ${price:.2f}; compare against simpler cables if you do not need extra features.")
    return facts[:limit]


def _humanize_feature(feature: str) -> str:
    lower = feature.lower()
    if "wired" in lower or "cable" in lower:
        return "Wired connection—no Bluetooth pairing required."
    if "4k" in lower and "60" in lower:
        return f"Supports {feature} for compatible TVs and sources."
    return feature if len(feature) < 100 else feature[:97] + "…"


def _caveat(product: dict[str, Any], session_context: dict[str, Any], review_intel: dict[str, Any]) -> str | None:
    reqs = " ".join(session_context.get("requirements") or []).lower()
    text = ((product.get("name") or "") + " " + " ".join((product.get("sourceFields") or {}).get("features") or [])).lower()
    if "120" in reqs and "120" not in text and "60" in text:
        return "listing tops out at 4K60, not 120Hz."
    if review_intel.get("complaints"):
        return review_intel["complaints"][0][:120]
    return None


def _recommendation_line(profile: str, session_context: dict[str, Any], caveat: str | None) -> str:
    if session_context.get("current_priority_override") == "image_quality_over_price":
        return "prioritize panel quality for this purchase even if it costs more."
    if profile == "compatibility_first":
        return "check port and refresh-rate compatibility before price."
    if profile == "value_first":
        return "it is a solid pick if the specs match what you will actually use."
    if caveat:
        return "worth considering if the trade-offs fit your setup."
    return "the listing looks reasonable based on catalog facts."


def _trade_line(profile: str, session_context: dict[str, Any]) -> str:
    if session_context.get("current_priority_override") == "image_quality_over_price":
        return "For this monitor search, picture quality outweighs saving a few dollars."
    if profile == "value_first":
        return "I would weigh whether premium specs justify the price for your use."
    if profile == "compatibility_first":
        return "Compatibility with your devices matters more than brand here."
    return ""


def _next_step(message: str, has_alts: bool) -> str:
    lower = message.lower()
    if "cheaper" in lower:
        return "Want me to line up cheaper options with the same constraints?"
    if has_alts:
        return "I can compare the top alternatives side by side."
    if "monitor" in lower:
        return "Share your budget and panel size if you want tighter criteria."
    return "Ask for reviews, cheaper options, or a comparison next."


def _product_refs(primary: dict[str, Any], alternatives: list[dict[str, Any]], message: str) -> list[dict[str, Any]]:
    refs = [_ref_row(primary, role="primary")]
    if "cheaper" in (message or "").lower():
        for alt in alternatives[:3]:
            if alt.get("id") != primary.get("id"):
                refs.append(_ref_row(alt, role="alternative"))
    return refs[:4]


def _ref_row(product: dict[str, Any], role: str) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    feature = (source.get("features") or [None])[0]
    return {
        "product_id": product.get("id"),
        "role": role,
        "title": _short_title(product),
        "brand": product.get("brand"),
        "price": reference_amount(product),
        "spec_line": str(feature)[:80] if feature else None,
    }


def _collapsed_details(
    primary: dict[str, Any],
    alternatives: list[dict[str, Any]],
    *,
    include_reviews: bool,
    expanded: bool = False,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    specs = _all_specs(primary)
    if specs:
        sections.append({
            "id": "specs",
            "title": "Full specs",
            "collapsed": not expanded,
            "lines": specs,
        })
    if alternatives:
        lines = []
        for alt in alternatives[:3]:
            p = reference_amount(alt)
            lines.append(f"{_short_title(alt)} — ${p:.2f}" if p else _short_title(alt))
        sections.append({"id": "alternatives", "title": "Alternatives", "collapsed": True, "lines": lines})
    return sections


def _all_specs(product: dict[str, Any]) -> list[str]:
    source = product.get("sourceFields") or {}
    lines = []
    for key, value in list((source.get("details") or {}).items())[:10]:
        lines.append(f"{key}: {value}")
    for feature in (source.get("features") or [])[:6]:
        if feature not in lines:
            lines.append(str(feature))
    return lines[:12]


def _review_lines(review_intel: dict[str, Any]) -> list[str]:
    lines = []
    if review_intel.get("summary"):
        lines.append(review_intel["summary"])
    for item in review_intel.get("sources") or []:
        snippet = item.get("snippet")
        if snippet:
            lines.append(snippet[:200])
    return lines[:6]


def _suggested_actions(
    message: str,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    intent: ShoppingIntent,
) -> list[dict[str, Any]]:
    lower = (message or "").lower()
    if not primary:
        return [
            {"id": "find-hdmi", "label": "Browse HDMI cables", "kind": "message", "message": "Show HDMI cables under $15"},
            {"id": "find-speaker", "label": "Find speakers", "kind": "message", "message": "Help me find a speaker for a small room"},
            {"id": "set-budget", "label": "Set a budget", "kind": "message", "message": "My budget is under $100"},
        ]
    if "review" in lower:
        return [
            {"id": "cheaper", "label": "Find cheaper", "kind": "quick", "action": "cheaper"},
            {"id": "compare", "label": "Compare options", "kind": "quick", "action": "compare"},
        ]
    if "cheaper" in lower or "compare" in lower:
        return [
            {"id": "why", "label": "Why this one?", "kind": "quick", "action": "why_this"},
            {"id": "reviews", "label": "Check reviews", "kind": "message", "message": "What do buyers think?"},
        ]
    return [
        {"id": "cheaper", "label": "Find cheaper", "kind": "quick", "action": "cheaper"},
        {"id": "reviews", "label": "Check reviews", "kind": "message", "message": "What do buyers think?"},
        {"id": "compare", "label": "Compare", "kind": "quick", "action": "compare"},
    ]


def to_legacy_structured(composed: dict[str, Any]) -> dict[str, Any]:
    return composed
