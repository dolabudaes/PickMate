from __future__ import annotations

from typing import Any

from .decision import hard_constraint_reason, score_product
from .risk import RiskEngine


class CounterfactualEngine:
    def __init__(self) -> None:
        self.risk = RiskEngine()

    def switch_conditions(self, products: list[dict[str, Any]], intent: dict[str, Any], profile: dict[str, Any], current_top_id: str | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        variants = [
            ("Prioritize price", "price_value", 1.0),
            ("Prioritize quality and reputation", "quality", 1.0),
            ("Avoid durability risk", "durability", 1.0),
            ("Frequent calls or meetings", "call_quality", 1.0),
            ("Prioritize comfort", "comfort", 1.0),
            ("Keep commute noise as the main scenario", "noise_cancellation", 1.0),
        ]
        for label, key, value in variants:
            variant_profile = {**profile, "priorities": {**profile.get("priorities", {}), key: value}}
            ranked = []
            for product in products:
                if hard_constraint_reason(product, intent, variant_profile):
                    continue
                risk = self.risk.evaluate(product, intent, variant_profile)
                ranked.append(score_product(product, intent, variant_profile, risk))
            ranked.sort(key=lambda item: item["score"], reverse=True)
            if ranked and ranked[0]["product"]["id"] != current_top_id:
                out.append({"condition": label, "new_primary": ranked[0]["product"], "reason": f"Reranked after increasing {key} weight"})
        seen = set()
        unique = []
        for item in out:
            key = (item["condition"], item["new_primary"]["id"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique[:3]
