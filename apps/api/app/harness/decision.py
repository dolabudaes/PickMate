from __future__ import annotations

import math
import re
from typing import Any


def hard_constraint_reason(product: dict[str, Any], intent: dict[str, Any], profile: dict[str, Any]) -> str:
    attrs = product["attributes"]
    budget_max = intent["budget"].get("max") or profile.get("budget", {}).get("max")
    category = str(intent.get("category") or "any").lower()
    if category != "any" and not category_matches_product(category, product):
        return "Product category does not match"
    source = product.get("sourceFields", {})
    brand_or_store = intent.get("hard_constraints", {}).get("brand_or_store")
    if brand_or_store:
        expected = str(brand_or_store).lower()
        values = [source.get("brand", ""), source.get("store", ""), product.get("brand", "")]
        if not any(expected in str(value).lower() for value in values):
            return "Brand or store does not match"
    for item in intent.get("hard_constraints", {}).get("required_attributes", []):
        if not detail_matches(source.get("details") or {}, item.get("field", ""), item.get("value", "")):
            return f"Detail field does not match: {item.get('field')}"
    if budget_max is not None and source.get("price") is None:
        return "Price is missing, so the budget cannot be verified"
    if budget_max is not None and product["currentPrice"] > budget_max:
        return f"Over budget by {format_money(product, product['currentPrice'] - budget_max)}"
    if intent["hard_constraints"].get("in_stock") and product["stockStatus"] == "out_of_stock":
        return "Currently out of stock"
    platform = intent["hard_constraints"].get("device_platform") or profile.get("device_platform")
    if platform == "android" and not attrs["androidCompatible"]:
        return "Not compatible with Android"
    if platform == "ios" and not attrs["iosCompatible"]:
        return "Not compatible with iOS"
    if intent["hard_constraints"].get("form_factor") and attrs["fitType"] != intent["hard_constraints"]["form_factor"]:
        return "Form factor does not match"
    if intent.get("avoid_deep_insertion") and attrs["inEarDepth"] == "deep":
        return "Deep in-ear fit"
    return ""


def format_money(product: dict[str, Any], amount: float | int) -> str:
    currency = str(product.get("currency") or "USD").upper()
    value = float(amount)
    if currency == "USD":
        return f"${value:.2f}"
    if currency == "CNY":
        return f"¥{value:g}"
    return f"{currency} {value:g}"


def score_product(product: dict[str, Any], intent: dict[str, Any], profile: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    attrs = product["attributes"]
    weights = merged_weights(intent, profile)
    budget_max = intent["budget"].get("max") or profile.get("budget", {}).get("max") or 800
    price_fit = 42 if product.get("sourceFields", {}).get("price") is None else max(40, min(100, 100 - product["currentPrice"] / budget_max * 30))
    compatibility = 95 if any(c in attrs["supportedCodecs"] for c in ["LDAC", "LHDC", "SSC", "L2HC"]) else 72
    comfort = attrs["comfortScore"] + (8 if attrs["smallEarFriendly"] else 0) - attrs["singleEarWeight"]
    quality = dimension_score(product, "quality")
    durability = dimension_score(product, "durability")
    review_confidence = dimension_score(product, "review_confidence")
    raw = (
        attrs["noiseCancellationScore"] * weights["noise_cancellation"]
        + comfort * weights["comfort"]
        + attrs["callScore"] * weights["call_quality"]
        + attrs["batteryHours"] * 8 * weights["battery"]
        + price_fit * weights["price_value"]
        + compatibility * weights["compatibility"]
        + water_score(attrs["waterResistance"]) * weights.get("water_resistance", 0)
        + (92 if attrs["multipoint"] else 58) * weights.get("multipoint", 0)
        + quality * weights.get("quality", 0)
        + durability * weights.get("durability", 0)
        + review_confidence * weights.get("review_confidence", 0)
    )
    source = product.get("sourceFields", {})
    coverage = min(12, len(product["priceHistory"]) / 2 + len(product["reviews"]) / 6 + len(product["videos"]) + len(source.get("features") or []) / 4 + len(source.get("details") or {}) / 10)
    match_bonus = query_match_bonus(product, intent) + len(intent.get("hard_constraints", {}).get("required_attributes", [])) * 2
    return {"product": product, "score": round(raw + coverage + match_bonus - risk["total_penalty"], 3), "weights": weights, "evidence_bonus": coverage}


def merged_weights(intent: dict[str, Any], profile: dict[str, Any]) -> dict[str, float]:
    weights = {
        "noise_cancellation": 0,
        "comfort": 0,
        "call_quality": 0,
        "battery": 0,
        "price_value": 0,
        "compatibility": 0,
        "water_resistance": 0,
        "multipoint": 0,
        "quality": 0,
        "durability": 0,
        "review_confidence": 0,
        **intent["priorities"],
    }
    for key, value in profile.get("priorities", {}).items():
        if key in weights:
            weights[key] = max(float(weights[key]), float(value))
    if profile.get("budget_preference") == "quality_first":
        weights["quality"] = max(weights["quality"], 0.86)
    if profile.get("risk_preference") == "risk_averse":
        weights["durability"] = max(weights["durability"], 0.78)
        weights["review_confidence"] = max(weights["review_confidence"], 0.72)
    total = sum(weights.values()) or 1
    return {key: round(value / total, 3) for key, value in weights.items()}


def water_score(value: str) -> int:
    if "7" in value:
        return 95
    if "5" in value:
        return 82
    if "4" in value:
        return 70
    return 55


def dimension_score(product: dict[str, Any], key: str) -> float:
    dims = product.get("standardizedDimensions") or {}
    if key in dims:
        return float(dims[key].get("score", 60))
    if key == "review_confidence":
        return review_confidence_score(product)
    if key == "quality":
        return rating_score(product.get("rating") or 0, product.get("reviewCount") or 0)
    if key == "durability":
        return keyword_score(product_text(product), ["durable", "durability", "sturdy", "long lasting", "耐用", "结实"], rating_score(product.get("rating") or 0, product.get("reviewCount") or 0))
    return 60


def product_text(product: dict[str, Any]) -> str:
    source = product.get("sourceFields", {})
    return " ".join([
        product.get("name", ""),
        product.get("description", ""),
        source.get("title", ""),
        source.get("mainCategory", ""),
        source.get("store", ""),
        " ".join(source.get("features") or []),
        " ".join(source.get("description") or []),
        " ".join(f"{key}: {value}" for key, value in (source.get("details") or {}).items()),
        " ".join(review.get("content", "") for review in product.get("reviews", [])[:20]),
    ]).lower()


def query_match_bonus(product: dict[str, Any], intent: dict[str, Any]) -> float:
    query = str(intent.get("product_query") or "").lower().strip()
    if len(query) < 2:
        return 0
    text = product_text(product)
    tokens = [token for token in re.findall(r"[a-z0-9][a-z0-9.\-]{1,}|[\u4e00-\u9fa5]{2,}", query) if len(token) > 1][:8]
    if not tokens:
        return 8 if query in text else 0
    matched = sum(1 for token in tokens if token in text)
    return min(14, matched * 2.5 + (4 if query in text else 0))


def detail_matches(details: dict[str, Any], field: str, value: str) -> bool:
    expected_field = str(field).lower()
    expected_value = str(value).lower()
    normalized = {str(k).lower(): str(v).lower() for k, v in details.items()}
    direct = normalized.get(expected_field)
    if direct:
        return expected_value in direct
    return any(expected_field in key and expected_value in val for key, val in normalized.items())


def keyword_score(text: str, keywords: list[str], default: float) -> float:
    hits = sum(1 for keyword in keywords if keyword.lower() in text)
    return max(35, min(96, default + hits * 7))


def rating_score(rating: float, rating_number: int) -> float:
    if not rating:
        return 58
    confidence = min(10, math.log10(max(int(rating_number), 1)) * 3)
    return max(35, min(100, float(rating) * 18 + confidence))


def review_confidence_score(product: dict[str, Any]) -> float:
    count = int(product.get("reviewCount") or 0)
    reviews = product.get("reviews") or []
    count_score = min(42, math.log10(max(count, 1)) * 14)
    verified = sum(1 for review in reviews if review.get("verifiedPurchase"))
    helpful = sum(int(review.get("helpfulCount") or 0) for review in reviews)
    return max(35, min(100, 42 + count_score + min(10, verified) + min(8, helpful / 50)))


def category_matches_product(category: str, product: dict[str, Any]) -> bool:
    product_category = str(product.get("category", "")).lower()
    if product_category == category or category in product_category:
        return True
    text = product_text(product)
    if category in {"headphones", "tws_anc_earbuds"}:
        return bool(re.search(r"earbuds?|headphones?|headset", text, re.I))
    if category == "soundbar":
        return "soundbar" in text or "sound bar" in text
    if category == "speaker":
        return "speaker" in text
    if category == "receiver":
        return "receiver" in text
    if category == "amplifier":
        return "amplifier" in text or re.search(r"\bamp\b", text)
    if category == "home theater":
        return "theater" in text or "theatre" in text or "surround" in text
    if category == "cable":
        return bool(re.search(r"hdmi|optical|toslink|cable", text, re.I))
    return category in text
