from __future__ import annotations

import re
from typing import Any

from .review_provider import fetch_review_intelligence
from .shopping_compare import reference_amount
from .taste_retriever import personalization_profile


def response_depth(message: str, action: str) -> str:
    text = (message or "").lower()
    if action in {"cheaper", "why_this"} or len(text.split()) <= 6:
        return "quick"
    if re.search(r"\bcompare\b|versus|vs\.|between these", text):
        return "deep"
    if re.search(r"\bgood\b|\breview|spec|worth|should i", text):
        return "brief"
    return "brief"


def build_product_brief(
    product: dict[str, Any],
    *,
    retrieved_taste: dict[str, Any],
    session_context: dict[str, Any],
    alternatives: list[dict[str, Any]] | None = None,
    depth: str = "brief",
) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    price = reference_amount(product)
    profile = personalization_profile(retrieved_taste)
    short_title = _short_title(product)
    overview = {
        "title": short_title,
        "brand": product.get("brand"),
        "reference_price": price,
        "currency": product.get("currency") or "USD",
        "category": product.get("category") or source.get("mainCategory"),
        "purpose": _purpose(product),
        "verdict": _verdict(product, profile, session_context),
    }
    highlights = _highlights(product, profile, session_context, depth)
    specs = _specs(product, depth)
    reviews = _review_intel(product)
    price_value = _price_value(product, alternatives or [], profile)
    limitations = _limitations(product, session_context, reviews)
    recommendation = _personalized_recommendation(product, profile, session_context, limitations)
    message = _compose_message(overview, highlights, reviews, price_value, limitations, recommendation, depth)

    return {
        "depth": depth,
        "message": message,
        "overview": overview,
        "highlights": highlights,
        "technical_specifications": specs,
        "review_intelligence": reviews,
        "price_value": price_value,
        "limitations": limitations,
        "personalized_recommendation": recommendation,
        "direct_recommendation": recommendation.get("summary"),
        "product_highlights": [item.get("title") or item.get("feature") for item in highlights if item.get("title") or item.get("feature")],
        "important_drawbacks": limitations,
        "customer_review_summary": reviews.get("summary"),
        "price_value_analysis": price_value.get("summary"),
        "product_comparisons": price_value.get("comparison_note"),
        "suggested_follow_up_questions": _follow_ups(profile, session_context),
    }


def _short_title(product: dict[str, Any]) -> str:
    name = product.get("name") or ""
    brand = product.get("brand") or ""
    if brand and name.lower().startswith(brand.lower()):
        name = name[len(brand) :].strip(" -–—")
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > 72:
        name = name[:69] + "…"
    return name or product.get("name") or "This product"


def _purpose(product: dict[str, Any]) -> str:
    text = " ".join((product.get("sourceFields") or {}).get("features") or [])[:200].lower()
    if "hdmi" in text or "hdmi" in (product.get("name") or "").lower():
        return "HDMI video/audio connection"
    return product.get("category") or "Home audio"


def _verdict(product: dict[str, Any], profile: str, context: dict[str, Any]) -> str:
    rating = product.get("rating")
    reviews = int(product.get("reviewCount") or 0)
    base = f"Catalog listing with {rating:.1f}/5 from {reviews} reviews." if rating and reviews else "Catalog listing with limited review evidence."
    reqs = context.get("requirements") or []
    if profile == "compatibility_first" and reqs:
        return f"{base} Compatibility details matter most for your {', '.join(reqs[:2])} setup."
    if profile == "value_first":
        price = reference_amount(product)
        if price is not None:
            return f"{base} Reference price ${price:.2f}—worth weighing against what you actually need."
    return base


def _highlights(product: dict[str, Any], profile: str, context: dict[str, Any], depth: str) -> list[dict[str, Any]]:
    source = product.get("sourceFields") or {}
    features = list(source.get("features") or [])[:8]
    details = source.get("details") or {}
    out: list[dict[str, Any]] = []
    limit = 2 if depth == "quick" else 5 if depth == "brief" else 6
    for feature in features[:limit]:
        item = {
            "feature": feature,
            "specification": feature,
            "benefit": _benefit_from_feature(feature),
            "personal_relevance": _personal_relevance(feature, profile, context),
        }
        out.append(item)
    for key, value in list(details.items())[: max(0, limit - len(out))]:
        text = f"{key}: {value}"
        out.append({
            "feature": key,
            "specification": str(value),
            "benefit": "Listed in catalog specifications",
            "personal_relevance": _personal_relevance(text, profile, context),
        })
    return out[:limit]


def _benefit_from_feature(feature: str) -> str:
    lower = feature.lower()
    if "120" in lower and "4k" in lower:
        return "Supports high refresh 4K where the device and TV both support it"
    if "60" in lower and "4k" in lower:
        return "Supports 4K at 60Hz"
    if "ethernet" in lower:
        return "HDMI with Ethernet channel for compatible setups"
    return "Practical capability described in the listing"


def _personal_relevance(feature: str, profile: str, context: dict[str, Any]) -> str:
    lower = feature.lower()
    reqs = " ".join(context.get("requirements") or []).lower()
    if "120" in reqs and "120" in lower:
        return "Matches your stated 4K 120Hz requirement"
    if "120" in reqs and "60" in lower and "120" not in lower:
        return "May not meet your 4K 120Hz requirement—verify before buying"
    if profile == "value_first" and "premium" in lower:
        return "Premium feature—only worth it if you will use it"
    if profile == "compatibility_first" and ("hdmi" in lower or "compatible" in lower):
        return "Check compatibility with your devices first"
    return ""


def _specs(product: dict[str, Any], depth: str) -> list[str]:
    source = product.get("sourceFields") or {}
    lines = []
    for key, value in list((source.get("details") or {}).items())[:8]:
        lines.append(f"{key}: {value}")
    for feature in (source.get("features") or [])[: max(0, 6 - len(lines))]:
        lines.append(feature)
    if depth == "quick":
        return lines[:2]
    return lines[:8]


def _review_intel(product: dict[str, Any]) -> dict[str, Any]:
    intel = fetch_review_intelligence(product)
    if intel.get("complaints") and intel.get("available"):
        intel["summary"] = f"{intel.get('summary', '')} Recurring complaints mention: {intel['complaints'][0][:120]}.".strip()
    elif intel.get("positives") and intel.get("available"):
        intel["summary"] = f"{intel.get('summary', '')} Buyers often mention: {intel['positives'][0][:120]}.".strip()
    return intel


def _price_value(product: dict[str, Any], alternatives: list[dict[str, Any]], profile: str) -> dict[str, Any]:
    price = reference_amount(product)
    lines = []
    if price is not None:
        lines.append(f"Catalog reference price: ${price:.2f} (not a live checkout price).")
    comparison_note = None
    if alternatives:
        alt = alternatives[0]
        alt_price = reference_amount(alt)
        if price is not None and alt_price is not None and alt_price != price:
            delta = price - alt_price
            comparison_note = f"Compared with { _short_title(alt) }: ${abs(delta):.2f} {'more' if delta > 0 else 'less'} on reference price."
            if profile == "value_first":
                lines.append(comparison_note)
    return {"summary": " ".join(lines), "comparison_note": comparison_note}


def _limitations(product: dict[str, Any], context: dict[str, Any], reviews: dict[str, Any]) -> list[str]:
    limits = []
    reqs = " ".join(context.get("requirements") or []).lower()
    text = (product.get("name") or "") + " " + " ".join((product.get("sourceFields") or {}).get("features") or [])
    if "120" in reqs and "120" not in text.lower() and "60" in text.lower():
        limits.append("Listing advertises 4K@60Hz; verify 120Hz support before using with a 4K 120Hz setup.")
    if not reviews.get("available"):
        limits.append("Review evidence is limited in the catalog.")
    if reference_amount(product) is None:
        limits.append("Reference price unavailable.")
    return limits[:4]


def _personalized_recommendation(product: dict[str, Any], profile: str, context: dict[str, Any], limitations: list[str]) -> dict[str, Any]:
    fits = True
    summary_parts = []
    if profile == "value_first":
        summary_parts.append("Strong fit if the advertised capabilities match what you need without paying for extras.")
    elif profile == "compatibility_first":
        summary_parts.append("Check device and TV compatibility before buying—specs matter more than brand here.")
    elif profile == "quality_first":
        summary_parts.append("For this purchase, picture quality matters more than shaving dollars off the price.")
    else:
        summary_parts.append("Reasonable catalog match based on verified listing facts.")
    if limitations:
        fits = "120" not in " ".join(limitations).lower() or "verify" not in limitations[0].lower()
    return {
        "fits_current_need": fits,
        "summary": " ".join(summary_parts),
        "next_step": "Want a cheaper option, a compatibility check, or a side-by-side compare?",
    }


def _compose_message(overview, highlights, reviews, price_value, limitations, recommendation, depth) -> str:
    parts = [overview.get("verdict") or ""]
    if depth != "quick" and highlights:
        lead = highlights[0]
        rel = lead.get("personal_relevance")
        if rel:
            parts.append(rel + ".")
    if price_value.get("summary"):
        parts.append(price_value["summary"])
    if limitations and depth != "quick":
        parts.append(f"Watch out: {limitations[0]}")
    if recommendation.get("summary"):
        parts.append(recommendation["summary"])
    return " ".join(part for part in parts if part).strip()


def _follow_ups(profile: str, context: dict[str, Any]) -> list[str]:
    if profile == "value_first":
        return ["Show a cheaper option", "Do I need 4K 120Hz for my setup?"]
    if profile == "compatibility_first":
        return ["Will this work with my PS5 and TV?", "Compare two HDMI options"]
    return ["Anything cheaper?", "Why this one?"]


def brief_to_structured_response(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": brief.get("message"),
        "direct_recommendation": brief.get("direct_recommendation"),
        "product_highlights": brief.get("product_highlights") or [],
        "technical_specifications": brief.get("technical_specifications") or [],
        "price_value_analysis": brief.get("price_value_analysis"),
        "customer_review_summary": brief.get("customer_review_summary"),
        "product_comparisons": brief.get("product_comparisons"),
        "important_drawbacks": brief.get("limitations") or [],
        "suggested_follow_up_questions": brief.get("suggested_follow_up_questions") or [],
        "product_brief": brief,
    }
