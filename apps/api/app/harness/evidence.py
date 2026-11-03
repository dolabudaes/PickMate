from __future__ import annotations

from typing import Any


class EvidenceFusion:
    def fuse(self, product: dict[str, Any], price: dict[str, Any], risk: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
        attrs = product["attributes"]
        source = product.get("sourceFields", {})
        dimensions = product.get("standardizedDimensions", {})
        product_db = source.get("schema") in {"pickmate_subset", "ecomagentbench_product_db"}
        review_summary = summarize_reviews(product, intent)
        strengths = [
            claim(field_match_claim(product, intent), [source.get("schema", "ProductDB"), "title/features/details"], 1, "strong" if source.get("features") or source.get("details") else "medium", "high"),
            claim(f"Rating evidence: {product.get('rating', 0):.1f}/5 from {product.get('reviewCount', 0)} reviews", ["average_rating", "rating_number"], 1, "strong" if product.get("reviewCount", 0) >= 100 else "medium", "high"),
        ]
        if not product_db:
            strengths.extend([
                claim(f"Noise cancellation score {attrs['noiseCancellationScore']}, suited to commute noise", ["ProductAttribute"], 1, "strong", "high" if "subway_commute" in intent["use_cases"] else "medium"),
                claim(f"Call score {attrs['callScore']}, microphone count {attrs['microphoneCount']}", ["ProductAttribute", "ReviewEvidence"], 2, "medium", "high" if "call_quality" in intent["explicit_concerns"] else "medium"),
            ])
        for key in intent.get("decision_dimensions", [])[:4]:
            dimension = dimensions.get(key)
            if dimension and dimension.get("evidence"):
                strengths.append(claim(f"{dimension['label']}: {dimension['evidence'][0]}", dimension.get("sources", ["details"]), 1, "medium", "high"))
        if not product_db and intent.get("small_ear_friendly") and attrs["smallEarFriendly"]:
            strengths.append(claim(f"Ear tip sizes include {', '.join(attrs['earTipSizes'])}", ["ProductAttribute", "ReviewEvidence"], 2, "medium", "high"))
        concerns = [claim(r["claim"], [r["source"]], 1, "medium", "high") for r in risk["relevant_risks"][:3]]
        conflicts = []
        if not product_db and intent.get("small_ear_friendly") and not attrs["smallEarFriendly"]:
            conflicts.append(claim("Fit feedback is mixed for smaller ears", ["ReviewEvidence", "ProductAttribute"], 2, "medium", "high"))
        insufficient = []
        if not product.get("reviews"):
            insufficient.append("Missing review text that can be cited")
        if not product.get("videos") and not product_db:
            insufficient.append("Limited video evidence")
        return {"price": price, "strengths": strengths, "concerns": concerns, "conflicts": conflicts, "review_summary": review_summary, "insufficient_evidence": insufficient}


def claim(text: str, sources: list[str], support_count: int, strength: str, relevance: str) -> dict[str, Any]:
    return {"claim": text, "source_types": sources, "support_count": support_count, "strength": strength, "relevance_to_user": relevance}


def field_match_claim(product: dict[str, Any], intent: dict[str, Any]) -> str:
    source = product.get("sourceFields", {})
    query = intent.get("product_query") or "this need"
    fields = []
    if source.get("title"):
        fields.append("title")
    if source.get("features"):
        fields.append("features")
    if source.get("details"):
        fields.append("details")
    return f"Matched {', '.join(fields) or 'product fields'} against \"{query}\""


def summarize_reviews(product: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    needs = intent.get("review_evidence_needs") or []
    reviews = product.get("reviews") or []
    selected = []
    for need in needs:
        hit = next((review for review in reviews if need.lower() in review.get("content", "").lower()), None)
        if hit:
            selected.append({
                "need": need,
                "rating": hit.get("rating"),
                "text": hit.get("content", ""),
                "helpful_vote": hit.get("helpfulCount", 0),
                "verified_purchase": hit.get("verifiedPurchase", False),
                "timestamp": hit.get("createdAt", ""),
            })
    if not selected and reviews:
        for review in sorted(reviews, key=lambda item: (item.get("verifiedPurchase", False), item.get("helpfulCount", 0)), reverse=True)[:3]:
            selected.append({
                "need": "general_review",
                "rating": review.get("rating"),
                "text": review.get("content", ""),
                "helpful_vote": review.get("helpfulCount", 0),
                "verified_purchase": review.get("verifiedPurchase", False),
                "timestamp": review.get("createdAt", ""),
            })
    return {"requested_review_needs": needs, "selected_reviews": selected[:5]}
