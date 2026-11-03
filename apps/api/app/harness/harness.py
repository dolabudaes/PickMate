from __future__ import annotations

import secrets
import time
from typing import Any

from ..schemas import HarnessRequest, HarnessResponse
from ..services.profile import apply_preference_update, save_profile
from .context import ContextBuilder
from .control import RecommendationControl
from .counterfactual import CounterfactualEngine
from .decision import hard_constraint_reason, score_product
from .evidence import EvidenceFusion
from .intent import IntentRouter, parse_intent
from .llm import get_llm_provider
from .regret import RegretGuard
from .risk import RiskEngine
from .tools import ToolRegistry
from .trace import save_run


class PickMateHarness:
    def __init__(self) -> None:
        self.tools = ToolRegistry()
        self.context_builder = ContextBuilder(self.tools)
        self.intent_router = IntentRouter()
        self.risk_engine = RiskEngine()
        self.evidence_fusion = EvidenceFusion()
        self.control = RecommendationControl()
        self.regret_guard = RegretGuard()
        self.counterfactual = CounterfactualEngine()
        self.llm = get_llm_provider()

    async def run(self, request: HarnessRequest) -> HarnessResponse:
        started = time.perf_counter()
        run_id = f"run-{secrets.token_hex(8)}"
        tool_calls: list[dict[str, Any]] = []
        fallback_used = False
        intent_type = self.intent_router.route(request.message, request.action, has_active_run=True)
        context = await self.context_builder.build(request, intent_type, tool_calls)
        profile = context["profile"]
        if intent_type == "PREFERENCE_UPDATE":
            profile, changed, _ = apply_preference_update(profile, request.message)
            if changed:
                save_profile(request.session_id, profile)
        intent = parse_intent(request.message, {"budget": profile.get("budget", {}), "priorities": profile.get("priorities", {}), "explicit_concerns": profile.get("explicit_concerns", [])})
        if intent_type == "PREFERENCE_UPDATE":
            intent = parse_intent(request.message, intent)
        if request.max_price is not None:
            current_max = intent.get("budget", {}).get("max")
            intent["budget"]["max"] = float(request.max_price) if current_max is None else min(float(current_max), float(request.max_price))
        exclude_ids = set(request.exclude_product_ids)
        products = context["products"]
        if not products:
            products = await self.tools.call(
                "ProductTool",
                {
                    "query": request.message or "home audio",
                    "category": None,
                    "max_price": intent.get("budget", {}).get("max"),
                },
                tool_calls,
            ) or []

        price_by_id: dict[str, Any] = {}
        for product in products[:8]:
            price_by_id[product["id"]] = await self.tools.call("PriceTool", {"product_id": product["id"]}, tool_calls)
            if intent_type in {"PRODUCT_RECOMMENDATION", "PRODUCT_COMPARISON", "PRODUCT_DECISION", "PRODUCT_RISK_QUERY"}:
                await self.tools.call("ReviewEvidenceTool", {"product_id": product["id"]}, tool_calls)
                await self.tools.call("VideoEvidenceTool", {"product_id": product["id"]}, tool_calls)

        excluded = []
        scored = []
        risk_by_id: dict[str, Any] = {}
        for product in products:
            if product["id"] in exclude_ids:
                excluded.append({"product": product, "reason": "Dismissed in this shopping session"})
                continue
            reason = hard_constraint_reason(product, intent, profile)
            if reason:
                excluded.append({"product": product, "reason": reason})
                continue
            risk = self.risk_engine.evaluate(product, intent, profile)
            risk_by_id[product["id"]] = risk
            scored.append(score_product(product, intent, profile, risk))
        if request.prefer_terms:
            terms = [term.lower() for term in request.prefer_terms if term]
            for item in scored:
                text = product_text(item["product"])
                hits = sum(1 for term in terms if term in text)
                if hits:
                    item["score"] += 6 * hits
        scored.sort(key=lambda item: item["score"], reverse=True)

        primary = self._recommendation_item(scored[0], "primary", intent, profile, price_by_id, risk_by_id) if scored else None
        alternatives = [self._recommendation_item(item, "budget" if idx == 0 else "specialist", intent, profile, price_by_id, risk_by_id) for idx, item in enumerate(self._alternatives(scored, primary))]
        control_result = self.control.verify(primary, alternatives, intent, profile)
        regret = self.regret_guard.build(primary, alternatives, profile, risk_by_id.get(primary["product"]["id"], {}) if primary else {})
        switches = self.counterfactual.switch_conditions(products, intent, profile, primary["product"]["id"] if primary else None)
        try:
            summary = await self.llm.summarize({"primary": primary, "alternatives": alternatives, "intent": intent, "regret": regret})
        except Exception:
            fallback_used = True
            summary = await get_llm_provider().summarize({"primary": primary, "alternatives": alternatives, "intent": intent, "regret": regret})

        evidence = primary.get("evidence_fusion", {}) if primary else {}
        response = {
            "run_id": run_id,
            "intent": intent,
            "primary": primary,
            "alternatives": alternatives,
            "evidence": evidence,
            "regret_guard": regret,
            "switch_conditions": switches,
            "clarification": None,
            "fallback_used": fallback_used,
            "trace_id": run_id,
            "excluded_products": excluded,
            "evidence_summary": summary,
            "missing_information": intent.get("missing_information", []),
            "data_updated_at": products[0]["dataUpdatedAt"] if products else "2026-08-06",
            "used_preferences": used_preference_labels(profile, intent),
        }
        trace = {
            "run_id": run_id,
            "session_id": request.session_id,
            "message": request.message,
            "intent_type": intent_type,
            "intent": intent,
            "selected_context": {k: v for k, v in context.items() if k != "products"},
            "tool_calls": tool_calls,
            "candidate_products": [p["id"] for p in products],
            "excluded_products": [{"product_id": e["product"]["id"], "reason": e["reason"]} for e in excluded],
            "scores": [{"product_id": s["product"]["id"], "score": s["score"], "weights": s["weights"]} for s in scored],
            "risk_penalties": risk_by_id,
            "evidence_summary": evidence,
            "control_result": control_result,
            "primary_product": primary["product"]["id"] if primary else None,
            "alternatives": [a["product"]["id"] for a in alternatives],
            "regret_guard": regret,
            "switch_conditions": [{"condition": s["condition"], "new_primary": s["new_primary"]["id"], "reason": s["reason"]} for s in switches],
            "fallback_used": fallback_used,
            "latency": round(time.perf_counter() - started, 4),
        }
        save_run(run_id, request.session_id, request.message, request.action, trace, response)
        return HarnessResponse(**response)

    def _recommendation_item(self, scored: dict[str, Any], role: str, intent: dict[str, Any], profile: dict[str, Any], price_by_id: dict[str, Any], risk_by_id: dict[str, Any]) -> dict[str, Any]:
        product = scored["product"]
        risk = risk_by_id.get(product["id"], {"relevant_risks": [], "ignored_risks": [], "total_penalty": 0})
        price = price_by_id.get(product["id"], {})
        fusion = self.evidence_fusion.fuse(product, price, risk, intent)
        return {
            "product": product,
            "score": scored["score"],
            "role": role,
            "reasons": reasons_for(product, intent),
            "cautions": cautions_for(product, risk),
            "regretGuard": "",
            "priceAnalysis": price_analysis_payload(product, price),
            "evidence": evidence_list(fusion, product),
            "relevantRisks": risk_evidence(risk),
            "evidence_fusion": fusion,
            "risk": risk,
        }

    def _alternatives(self, scored: list[dict[str, Any]], primary: dict[str, Any] | None) -> list[dict[str, Any]]:
        primary_id = primary["product"]["id"] if primary else None
        rest = [s for s in scored if s["product"]["id"] != primary_id]
        if not rest:
            return []
        budget = sorted(rest, key=lambda s: s["product"]["currentPrice"])[0]
        specialist = sorted([s for s in rest if s["product"]["id"] != budget["product"]["id"]], key=lambda s: max(s["product"]["attributes"]["callScore"], s["product"]["attributes"]["comfortScore"]), reverse=True)
        return [budget, *(specialist[:1])]


def used_preference_labels(profile: dict[str, Any], intent: dict[str, Any]) -> list[str]:
    labels = []
    for item in profile.get("preferences", []):
        if item.get("source") not in {"explicit", "confirmed"}:
            continue
        if item.get("value") == "dismissed":
            continue
        key = str(item.get("preference") or "")
        if key == "budget_max" and (intent.get("budget") or {}).get("max") is None and (profile.get("budget") or {}).get("max") is not None:
            labels.append("Using your saved preference: Budget range.")
        elif key in (profile.get("priorities") or {}) and key in (intent.get("priorities") or {}):
            labels.append(f"Using your saved preference: {key.replace('_', ' ').title()}.")
    return labels[:3]


def reasons_for(product: dict[str, Any], intent: dict[str, Any]) -> list[str]:
    attrs = product["attributes"]
    source = product.get("sourceFields", {})
    product_db = is_product_db_product(product)
    reasons = []
    query = str(intent.get("product_query") or "").strip()
    if query and query.lower() in product_text(product):
        reasons.append(f'Title or details match "{query}"')
    matched_attrs = matched_required_attributes(source.get("details") or {}, intent.get("hard_constraints", {}).get("required_attributes", []))
    if matched_attrs:
        reasons.append(f"Detail fields match: {', '.join(matched_attrs[:2])}")
    if "quality" in intent.get("explicit_concerns", []):
        reasons.append(f"Rating evidence: {product.get('rating', 0):.1f}/5 from {product.get('reviewCount', 0)} reviews")
    if not product_db and "subway_commute" in intent["use_cases"]:
        reasons.append(f"Noise cancellation score for commute noise: {attrs['noiseCancellationScore']}")
    if not product_db and intent.get("small_ear_friendly") and attrs["smallEarFriendly"]:
        reasons.append(f"Includes {', '.join(attrs['earTipSizes'])} ear tip sizes for smaller ears")
    if not product_db and intent["hard_constraints"].get("device_platform") == "android":
        reasons.append(f"Supports common Android codecs: {', '.join(attrs['supportedCodecs'])}")
    if not product_db and "call_quality" in intent.get("explicit_concerns", []):
        reasons.append(f"Call score {attrs['callScore']}, microphone count {attrs['microphoneCount']}")
    if not reasons and source.get("features"):
        reasons.append(f"Product feature: {source['features'][0]}")
    if not reasons:
        reasons.append(f"Rating evidence: {product.get('rating', 0):.1f}/5 from {product.get('reviewCount', 0)} reviews")
    return reasons[:3]


def is_product_db_product(product: dict[str, Any]) -> bool:
    return product.get("sourceFields", {}).get("schema") in {"pickmate_subset", "ecomagentbench_product_db"}


def cautions_for(product: dict[str, Any], risk: dict[str, Any]) -> list[str]:
    cautions = [r["claim"] for r in risk.get("relevant_risks", [])]
    cautions.extend(product.get("negativeThemes", [])[:2])
    return list(dict.fromkeys(cautions))[:2]


def price_analysis_payload(product: dict[str, Any], price: dict[str, Any]) -> dict[str, Any]:
    status_map = {"near_low": "Near historical low", "good": "Good recent price", "normal": "Typical price", "high": "High price", "insufficient": "Insufficient price data"}
    status = status_map.get(price.get("status"), "Insufficient price data")
    avg = price.get("average_90d")
    low = price.get("lowest_90d")
    delta_avg = price.get("current_vs_avg")
    delta_low = price.get("current_vs_low")
    if avg is None:
        explanation = "Not enough price samples to make a reliable price call."
    else:
        explanation = f"Current price is {money(product, product['currentPrice'])}, {'above' if delta_avg >= 0 else 'below'} the 90-day average by {money(product, abs(delta_avg))}, and above the 90-day low by {money(product, max(0, delta_low))}."
    return {"status": status, "average30": price.get("average_30d"), "average90": avg, "low90": low, "high90": price.get("highest_90d"), "deltaFrom90Average": delta_avg, "deltaFrom90Low": delta_low, "explanation": explanation}


def evidence_list(fusion: dict[str, Any], product: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    price = fusion.get("price", {})
    if price:
        out.append({"type": "price", "title": price_analysis_status(price), "detail": f"Current {money(product, price.get('current_price'))}; 90-day average {money(product, price.get('average_90d'))}; low {money(product, price.get('lowest_90d'))}.", "source": "PriceTool", "strength": "strong"})
    review_summary = fusion.get("review_summary") or {}
    selected_reviews = review_summary.get("selected_reviews") or []
    if selected_reviews:
        first = selected_reviews[0]
        out.append({
            "type": "review",
            "title": "Review evidence",
            "detail": f"{first.get('rating')} stars, helpful={first.get('helpful_vote')}, verified={first.get('verified_purchase')}: {first.get('text')}",
            "source": "reviews.rating/text/helpful_vote/verified_purchase/timestamp",
            "strength": "strong" if first.get("verified_purchase") or first.get("helpful_vote", 0) else "medium",
        })
    for item in fusion.get("strengths", [])[:2]:
        evidence_type = "details" if any("details" in source for source in item["source_types"]) else "review" if any("average_rating" in source or "rating_number" in source for source in item["source_types"]) else "attribute"
        out.append({"type": evidence_type, "title": item["claim"], "detail": item["claim"], "source": " + ".join(item["source_types"]), "strength": item["strength"]})
    for item in fusion.get("concerns", [])[:2]:
        out.append({"type": "video", "title": item["claim"], "detail": item["claim"], "source": " + ".join(item["source_types"]), "strength": item["strength"]})
    if fusion.get("insufficient_evidence"):
        out.append({"type": "insufficient", "title": "Insufficient video evidence", "detail": "There is limited video evidence.", "source": "VideoEvidenceTool", "strength": "weak"})
    return out


def money(product: dict[str, Any], amount: Any) -> str:
    if amount is None:
        return "Not provided"
    currency = product.get("currency") or "USD"
    value = float(amount)
    if currency == "USD":
        return f"${value:.2f}"
    if currency == "CNY":
        return f"¥{value:g}"
    return f"{currency} {value:g}"


def price_analysis_status(price: dict[str, Any]) -> str:
    return {"near_low": "Near historical low", "good": "Good recent price", "normal": "Typical price", "high": "High price", "insufficient": "Insufficient price data"}.get(price.get("status"), "Insufficient price data")


def risk_evidence(risk: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"type": "video", "title": r["claim"], "detail": r["reason"], "source": r["source"], "strength": "medium"} for r in risk.get("relevant_risks", [])[:3]]


def matched_required_attributes(details: dict[str, Any], required: list[dict[str, Any]]) -> list[str]:
    normalized = {str(key).lower(): str(value).lower() for key, value in details.items()}
    out = []
    for item in required:
        field = str(item.get("field", "")).lower()
        value = str(item.get("value", "")).lower()
        direct = normalized.get(field)
        if (direct and value in direct) or any(field in key and value in val for key, val in normalized.items()):
            out.append(f"{item.get('field')}={item.get('value')}")
    return out


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
