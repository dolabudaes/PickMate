from __future__ import annotations

import json
import os
import re
from typing import Any

from .shopping_compare import reference_amount

DEFAULT_WEIGHTS = {
    "compatibility": 3.0,
    "spec_coverage": 2.5,
    "price_value": 2.0,
    "quality_evidence": 1.5,
    "taste_alignment": 2.0,
    "brand_penalty": 1.0,
}


def rank_weights() -> dict[str, float]:
    raw = os.getenv("PICKI_RANK_WEIGHTS")
    if not raw:
        return dict(DEFAULT_WEIGHTS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in parsed.items()}}
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return dict(DEFAULT_WEIGHTS)


def personalized_rerank(
    candidates: list[dict[str, Any]],
    *,
    shopping_context: dict[str, Any],
    retrieved_taste: dict[str, Any],
    reference_product: dict[str, Any] | None = None,
    goal: str | None = None,
) -> list[dict[str, Any]]:
    """Return candidates sorted best-first with ranking_reasons attached (ephemeral)."""
    if not candidates:
        return []
    if len(candidates) == 1:
        return [_attach_reason(candidates[0], ["Only valid candidate"])]

    weights = rank_weights()
    requirements = [str(x).lower() for x in (shopping_context.get("requirements") or shopping_context.get("hard_constraints") or [])]
    devices = [str(x).lower() for x in (shopping_context.get("devices") or [])]
    taste_labels = _taste_labels(retrieved_taste)
    compatibility_strength = _preference_strength(retrieved_taste, ("compatib", "兼容", "适配"))
    value_strength = _preference_strength(retrieved_taste, ("good value", "value over", "性价比", "价格"))
    ref_price = reference_amount(reference_product) if reference_product else None
    scored: list[tuple[float, dict[str, Any], list[str]]] = []

    for product in candidates:
        pid = product.get("id")
        if pid in (shopping_context.get("rejected_product_ids") or []):
            continue
        reasons: list[str] = []
        score = 0.0
        blob = _blob(product)

        compat = 0.0
        if devices:
            if any(d in blob for d in devices):
                compat += 1.0
                reasons.append(f"Matches device context ({', '.join(devices[:2])})")
        if shopping_context.get("category_hint") == "hdmi" and "hdmi" in blob:
            compat += 1.0
            reasons.append("HDMI category match")
        score += compat * weights["compatibility"]

        spec = 0.0
        for req in requirements:
            if "4k" in req and "120" in req:
                if re.search(r"4k.*120|120.*hz|48\s*gbps|2\.1", blob, re.I):
                    spec += 1.0
                    reasons.append("Mentions 4K/high refresh capability in catalog text")
            elif req.lower() in blob:
                spec += 0.5
        score += spec * weights["spec_coverage"]

        price = reference_amount(product)
        if goal == "find_cheaper" and ref_price is not None and price is not None:
            if price < ref_price:
                delta = ref_price - price
                score += min(2.0, delta / max(ref_price, 1)) * weights["price_value"]
                reasons.append(f"Lower catalog price than reference (${price:.2f} vs ${ref_price:.2f})")
            elif price >= ref_price:
                score -= 0.5 * weights["price_value"]
        elif any(token in taste_labels for token in ("good value", "性价比优先", "价格优先")) and price is not None and ref_price is not None and price <= ref_price:
            score += 0.8 * value_strength * weights["price_value"]
            reasons.append("Better value vs reference under Good value preference")

        rating = product.get("rating")
        review_count = int(product.get("reviewCount") or 0)
        if rating is not None and review_count > 0:
            score += min(float(rating) / 5.0, 1.0) * weights["quality_evidence"]
            reasons.append(f"Catalog rating {rating} ({review_count} reviews)")
        elif review_count == 0:
            reasons.append("No review evidence in catalog")

        taste_score = 0.0
        if ("compatibility first" in taste_labels or "兼容性优先" in taste_labels) and compat > 0:
            taste_score += compatibility_strength
            reasons.append("Aligns with Compatibility first taste")
        if "brand isn't a priority" in taste_labels or "brand" in taste_labels:
            taste_score += 0.3
        score += taste_score * weights["taste_alignment"]

        if "brand isn't a priority" in taste_labels:
            brand = (product.get("brand") or "").lower()
            if brand and reference_product and brand == (reference_product.get("brand") or "").lower():
                score += 0.2 * weights["brand_penalty"]
            elif brand and reference_product and brand != (reference_product.get("brand") or "").lower():
                score += 0.4 * weights["taste_alignment"]
                reasons.append("Non-reference brand acceptable per taste")

        scored.append((score, product, reasons[:6]))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [_attach_reason(p, r) for _, p, r in scored]


def _attach_reason(product: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    out = dict(product)
    out["_ranking_reasons"] = reasons
    out["_ranking_score"] = None
    return out


def _blob(product: dict[str, Any]) -> str:
    source = product.get("sourceFields") or {}
    parts = [
        product.get("name") or "",
        product.get("title") or "",
        product.get("brand") or "",
        " ".join(source.get("features") or []),
        " ".join(f"{k} {v}" for k, v in (source.get("details") or {}).items()),
    ]
    return " ".join(parts).lower()


def _taste_labels(retrieved: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for bucket in ("global", "category_specific"):
        for item in retrieved.get(bucket) or []:
            text = (item.get("normalized_preference") or item.get("label") or "").lower()
            if text:
                labels.append(text)
    for label in retrieved.get("priority_labels") or []:
        labels.append(str(label).lower())
    return labels


def _preference_strength(retrieved: dict[str, Any], tokens: tuple[str, ...]) -> float:
    for bucket in ("category_specific", "global"):
        for item in retrieved.get(bucket) or []:
            label = str(item.get("normalized_preference") or item.get("label") or "").lower()
            if any(token in label for token in tokens):
                priority = max(0, min(100, int(item.get("priority") or 50)))
                return max(0.4, min(1.6, priority / 50))
    return 1.0
