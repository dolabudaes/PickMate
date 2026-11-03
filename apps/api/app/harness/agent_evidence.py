from __future__ import annotations

import re
from typing import Any

from .agent_schemas import EvidenceKind


def tag_field(field: str, source: str) -> dict[str, Any]:
    kind: EvidenceKind
    if source in {"reviews", "review"}:
        kind = "customer_review_opinion"
    elif source in {"features", "details", "title", "catalog"}:
        kind = "verified_catalog_fact"
    elif source in {"description", "manufacturer"}:
        kind = "manufacturer_claim"
    elif source == "model":
        kind = "model_analysis"
    else:
        kind = "missing_or_uncertain"
    return {"field": field, "kind": kind, "source": source}


def build_product_evidence(product: dict[str, Any]) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    reviews = product.get("reviews") or []
    price = source.get("price")
    rating = product.get("rating")
    review_count = int(product.get("reviewCount") or 0)
    facts: list[dict[str, Any]] = []
    if price is not None:
        facts.append(tag_field(f"Reference price: {price}", "catalog"))
    if rating is not None:
        facts.append(tag_field(f"Average rating: {rating} ({review_count} reviews)", "catalog"))
    for feature in (source.get("features") or [])[:5]:
        facts.append(tag_field(str(feature), "features"))
    for key, value in list((source.get("details") or {}).items())[:8]:
        facts.append(tag_field(f"{key}: {value}", "details"))
    review_samples = []
    for review in reviews[:3]:
        review_samples.append({
            **tag_field(review.get("content", "")[:240], "reviews"),
            "rating": review.get("rating"),
            "verified": review.get("verifiedPurchase", False),
        })
    missing = []
    if review_count == 0:
        missing.append("No customer reviews in catalog")
    if price is None:
        missing.append("Reference price unavailable")
    if not source.get("details"):
        missing.append("Detailed specifications limited in catalog")
    return {
        "product_id": product.get("id"),
        "facts": facts,
        "review_samples": review_samples,
        "missing": missing,
    }


def validate_structured_claims(structured: dict[str, Any], evidence_index: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text_blob = " ".join(
        str(structured.get(key) or "")
        for key in [
            "direct_recommendation",
            "price_value_analysis",
            "customer_review_summary",
            "product_comparisons",
            "message",
        ]
    )
    text_blob += " " + " ".join(structured.get("product_highlights") or [])
    text_blob += " " + " ".join(structured.get("technical_specifications") or [])
    if re.search(r"\b(certified|ul listed|fda|lifetime warranty)\b", text_blob, re.I):
        if not _supported_in_evidence(text_blob, evidence_index):
            failures.append("Unsupported certification or warranty claim")
    if re.search(r"\b\d+\s*(happy|verified)?\s*customers\b", text_blob, re.I):
        failures.append("Unsupported customer count claim")
    if re.search(r"\blive price\b", text_blob, re.I):
        failures.append("Live price wording is not allowed; use catalog reference price")
    return failures


def _supported_in_evidence(text: str, evidence_index: dict[str, Any]) -> bool:
    lowered = text.lower()
    for item in evidence_index.get("facts", []):
        if str(item.get("field", "")).lower() in lowered:
            return True
    return False


def sanitize_structured(structured: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    if not failures:
        return structured
    notes = list(structured.get("evidence_notes") or [])
    notes.append("Some model phrasing was adjusted to match verified catalog evidence.")
    structured["evidence_notes"] = notes[:6]
    if any("review" in failure.lower() for failure in failures):
        structured["customer_review_summary"] = "Customer review text is limited or unavailable in the catalog for this answer."
    if any("price" in failure.lower() for failure in failures):
        structured["price_value_analysis"] = "Price analysis uses catalog reference prices only."
    return structured
