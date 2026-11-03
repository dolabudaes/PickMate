from __future__ import annotations

from typing import Any


class RiskEngine:
    def evaluate(self, product: dict[str, Any], intent: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        penalty = 0.0
        relevant: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        concerns = set(intent.get("explicit_concerns", [])) | set(profile.get("explicit_concerns", []))
        small_ear = intent.get("small_ear_friendly") or profile.get("small_ear_friendly")
        product_db = product.get("sourceFields", {}).get("schema") in {"pickmate_subset", "ecomagentbench_product_db"}
        for video in product.get("videos", []):
            impact = video["impactType"]
            finding_type = video["findingType"]
            amount = 0.0
            reason = ""
            if finding_type == "call_quality_issue" and "call_quality" in concerns:
                amount = 24 if product["attributes"]["callScore"] <= 84 else 6
                reason = "You raised call/meeting priority, so this video risk is relevant to the use case"
            elif finding_type == "fit_issue" and small_ear:
                amount = 18
                reason = "You emphasized smaller-ear fit or long-wear comfort, so mixed fit feedback matters"
            elif impact == "appearance_only" and "appearance" not in concerns:
                reason = "This mainly affects appearance and is weakly related to the current core need"
            elif impact == "minor_interaction":
                amount = 4
                reason = "Minor interaction issue; small penalty only"
            if amount:
                penalty += amount
                relevant.append({"claim": video["finding"], "penalty": amount, "reason": reason, "source": video["videoTitle"]})
            else:
                ignored.append({"claim": video["finding"], "reason": reason or "Not sufficiently relevant to the current need", "source": video["videoTitle"]})
        if not product_db and small_ear and not product["attributes"]["smallEarFriendly"]:
            penalty += 16
            relevant.append({"claim": "Fit feedback is mixed for smaller ears", "penalty": 16, "reason": "User asked for smaller-ear friendly fit", "source": "Review + ProductAttribute"})
        if not product_db and "call_quality" in concerns and product["attributes"]["callScore"] <= 84:
            penalty += 20
            relevant.append({"claim": "Call score is below the high-frequency meeting threshold", "penalty": 20, "reason": "User added frequent calls or meetings", "source": "ProductAttribute"})
        review_risks = review_risk_signals(product, concerns)
        for item in review_risks:
            penalty += item["penalty"]
            relevant.append(item)
        rating = float(product.get("rating") or 0)
        review_count = int(product.get("reviewCount") or 0)
        if rating and rating < 3.8:
            amount = 10 if "quality" in concerns else 5
            penalty += amount
            relevant.append({
                "claim": f"Average rating is low: {rating:.1f}",
                "penalty": amount,
                "reason": "Low rating matters because the user cares about quality/review evidence" if "quality" in concerns else "Low rating is treated as a general risk",
                "source": "average_rating",
            })
        if review_count < 20 and "review_confidence" in profile.get("priorities", {}):
            penalty += 4
            relevant.append({
                "claim": "Review count is low",
                "penalty": 4,
                "reason": "The review sample is small, so evidence strength is weaker",
                "source": "rating_number",
            })
        return {"total_penalty": round(penalty, 3), "relevant_risks": relevant, "ignored_risks": ignored, "risk_reasons": [r["reason"] for r in relevant]}


def review_risk_signals(product: dict[str, Any], concerns: set[str]) -> list[dict[str, Any]]:
    keywords = {
        "durability": ["broken", "broke", "stopped working", "durability", "not last", "坏", "断", "不耐用"],
        "compatibility": ["not compatible", "doesn't fit", "did not fit", "incompatible", "不兼容", "不适配"],
        "quality": ["poor quality", "cheap", "defective", "质量差", "做工差", "瑕疵"],
    }
    out = []
    for review in product.get("reviews", []):
        content = str(review.get("content", ""))
        rating = float(review.get("rating") or 0)
        for key, words in keywords.items():
            if key in concerns and any(word.lower() in content.lower() for word in words):
                out.append({
                    "claim": content[:80],
                    "penalty": 12 if rating <= 2 else 7,
                    "reason": f"Review text contains negative evidence related to {key}",
                    "source": f"reviews helpful={review.get('helpfulCount', 0)} verified={review.get('verifiedPurchase', False)}",
                })
                break
        if len(out) >= 3:
            break
    return out
