from __future__ import annotations

from typing import Any

from .decision import hard_constraint_reason


class RecommendationControl:
    def verify(self, primary: dict[str, Any] | None, alternatives: list[dict[str, Any]], intent: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        removed: list[str] = []
        issues: list[str] = []
        for item in [p for p in [primary, *alternatives] if p]:
            reason = hard_constraint_reason(item["product"], intent, profile)
            if reason:
                item["control_excluded"] = reason
                issues.append(f"{item['product']['id']}: {reason}")
            safe_reasons = []
            evidence_text = " ".join(e["claim"] for e in item.get("evidence_fusion", {}).get("strengths", []))
            for r in item.get("reasons", []):
                smaller_ear_claim = "小耳" in r or "smaller ear" in r.lower()
                smaller_ear_evidence = "小耳" in evidence_text or "smaller ear" in evidence_text.lower() or "ear tip" in evidence_text.lower()
                if smaller_ear_claim and not smaller_ear_evidence:
                    removed.append(r)
                    continue
                safe_reasons.append(r)
            item["reasons"] = safe_reasons or ["Passed budget, stock, compatibility, and evidence-binding checks."]
        return {"passed": not issues, "issues": issues, "removed_unsupported_claims": removed}
