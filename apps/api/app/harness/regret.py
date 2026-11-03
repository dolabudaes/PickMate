from __future__ import annotations

from typing import Any


class RegretGuard:
    def build(self, primary: dict[str, Any] | None, alternatives: list[dict[str, Any]], profile: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
        if not primary:
            return {"most_likely_regret": "No product matches the hard constraints", "why_it_matters": "The budget or constraints need to be relaxed", "switch_condition": "Relax the budget or compatibility constraints and rerun the recommendation"}
        product = primary["product"]
        top_risk = (risk.get("relevant_risks") or [{}])[0]
        if top_risk:
            target = best_alternative_for(top_risk["claim"], alternatives)
            return {
                "most_likely_regret": top_risk["claim"],
                "why_it_matters": top_risk["reason"],
                "switch_condition": f"If this risk becomes a frequent scenario, consider {target}" if target else "If this risk is unacceptable, consider an alternative.",
            }
        weakness = (product.get("notFor") or product.get("negativeThemes") or ["The first pick may change if your needs change"])[0]
        target = alternatives[0]["product"]["name"] if alternatives else None
        return {
            "most_likely_regret": weakness,
            "why_it_matters": "This is the main tradeoff in the current first pick",
            "switch_condition": f"If this matters more, consider {target}" if target else "If this tradeoff is unacceptable, relax the budget and search again.",
        }


def best_alternative_for(claim: str, alternatives: list[dict[str, Any]]) -> str | None:
    if not alternatives:
        return None
    lowered = claim.lower()
    if "通话" in claim or "会议" in claim or "call" in lowered or "meeting" in lowered:
        return max(alternatives, key=lambda a: a["product"]["attributes"]["callScore"])["product"]["name"]
    if "小耳" in claim or "佩戴" in claim or "smaller ear" in lowered or "fit" in lowered:
        return max(alternatives, key=lambda a: a["product"]["attributes"]["comfortScore"])["product"]["name"]
    return alternatives[0]["product"]["name"]
