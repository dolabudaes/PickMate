from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..harness.agent_evidence import build_product_evidence, sanitize_structured, validate_structured_claims
from .picki_llm import chat_json, llm_configured
from .picki_response import compose_pick_response, pick_response_mode
from .product_relevance import (
    DISPLAY_MONITOR,
    GENERIC_AUDIO,
    HDMI_CABLE,
    HDMI_DVI,
    HEADPHONES,
    PRODUCT_FOCUS,
    SPEAKER,
    SOUNDBAR,
    UNKNOWN,
    ShoppingIntent,
    detect_shopping_intent,
    no_match_message,
    search_query_for_intent,
)
from .review_provider import fetch_review_intelligence
from .shopping_compare import reference_amount
from .taste_consolidator import apply_operations

TURN_GOALS = {
    "research",
    "find_cheaper",
    "compare",
    "discover_similar",
    "general",
    "clarify",
    "save",
    "cart",
    "reviews",
    "compatibility",
    "budget_update",
    "preference_update",
}
_CATEGORY_KINDS = {
    DISPLAY_MONITOR,
    HDMI_CABLE,
    HDMI_DVI,
    HEADPHONES,
    SPEAKER,
    SOUNDBAR,
    GENERIC_AUDIO,
    PRODUCT_FOCUS,
    UNKNOWN,
}


@dataclass
class TurnInterpretation:
    turn_goal: str = "general"
    category_kind: str = UNKNOWN
    search_query: str | None = None
    reference_product_ids: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)
    new_requirements: list[str] = field(default_factory=list)
    removed_constraints: list[str] = field(default_factory=list)
    clarification_needed: str | None = None
    preference_updates: list[dict[str, Any]] = field(default_factory=list)
    response_depth: str = "STANDARD"
    conversation_summary: str | None = None
    source: str = "rules"

    def to_shopping_intent(self) -> ShoppingIntent:
        kind = self.category_kind if self.category_kind in _CATEGORY_KINDS else UNKNOWN
        query = self.search_query
        reject = "studio_monitor_headphones" if kind == DISPLAY_MONITOR else None
        return ShoppingIntent(kind, query=query, reject_reason=reject)


async def interpret_shopping_turn(
    *,
    message: str,
    product_id: str | None,
    session_context: dict[str, Any],
    focus_product_ids: list[str],
    retrieved_taste: dict[str, Any],
    recent_messages: list[dict[str, str]] | None = None,
    shopping_state: Any | None = None,
    use_llm: bool,
) -> TurnInterpretation:
    from .shopping_conversation_state import resolve_product_references

    resolved_refs = resolve_product_references(
        message,
        product_id=product_id,
        shop_state=shopping_state,
        session_context=session_context,
    ) if shopping_state else list(focus_product_ids or [])
    rule = _interpret_rules(
        message,
        product_id=product_id,
        session_context=session_context,
        focus_product_ids=resolved_refs or focus_product_ids,
        shopping_state=shopping_state,
    )
    if not use_llm or not llm_configured():
        return rule
    llm = await _interpret_llm(
        message=message,
        product_id=product_id,
        session_context=session_context,
        focus_product_ids=focus_product_ids,
        retrieved_taste=retrieved_taste,
        recent_messages=recent_messages or [],
        shopping_state=shopping_state,
        rule_baseline=rule,
    )
    if not llm:
        return rule
    return _merge_interpretation(rule, llm)


def build_validated_plan(
    interpretation: TurnInterpretation,
    context: dict[str, Any],
    prior_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    message = (context.get("user_message") or "").lower()
    focus = list(interpretation.reference_product_ids or context.get("focus_product_ids") or [])
    executed = {item.get("tool") for item in prior_results}
    intent = interpretation.to_shopping_intent()
    calls: list[dict[str, Any]] = []
    goal = interpretation.turn_goal

    if "get_cart" not in executed and ("cart" in message or "my picks" in message):
        calls.append({"name": "get_cart", "arguments": {}})

    if focus and "get_product_details" not in executed and goal in {
        "research",
        "find_cheaper",
        "compare",
        "general",
    }:
        calls.append({"name": "get_product_details", "arguments": {"product_ids": focus[:3]}})

    if goal == "find_cheaper" and "search_products" not in executed:
        query = interpretation.search_query or search_query_for_intent(intent, context.get("user_message") or "")
        calls.append({"name": "search_products", "arguments": {"query": query, "filters": {}}})

    if goal == "compare" and len(focus) >= 2 and "compare_products" not in executed:
        compare_ids = focus[:4]
        if len(compare_ids) < 2 and len(context.get("compared_product_ids") or []) >= 2:
            compare_ids = list(context["compared_product_ids"][:4])
        if len(compare_ids) >= 2:
            calls.append({"name": "compare_products", "arguments": {"product_ids": compare_ids, "criteria": ["price", "rating"]}})

    if focus and any(token in message for token in ("review", "customer", "feedback", "buyers")) and "get_product_reviews" not in executed:
        calls.append({"name": "get_product_reviews", "arguments": {"product_ids": focus[:2]}})

    if "get_user_preferences" not in executed and any(token in message for token in ("taste", "preference", "usually", "remember")):
        calls.append({"name": "get_user_preferences", "arguments": {}})

    if goal in {"discover_similar", "research", "general"} and "search_products" not in executed:
        if goal != "find_cheaper":
            query = interpretation.search_query or search_query_for_intent(intent, context.get("user_message") or "")
            if query and (len(message) > 3 or goal == "discover_similar"):
                calls.append({"name": "search_products", "arguments": {"query": query, "filters": {}}})

    if not calls and focus and "get_product_reviews" not in executed and interpretation.response_depth == "DEEP":
        calls.append({"name": "get_product_reviews", "arguments": {"product_ids": focus[:1]}})

    if not calls and not focus and goal not in {"clarify"}:
        query = interpretation.search_query or search_query_for_intent(intent, message) or "home audio"
        calls.append({"name": "search_products", "arguments": {"query": query, "filters": {}}})

    return calls[:3]


def apply_interpretation_taste(session_id: str, conversation_id: str, interpretation: TurnInterpretation, message: str) -> list[dict[str, Any]]:
    """Only persist explicit long-term preferences; skip session/ephemeral signals."""
    operations: list[dict[str, Any]] = []
    ephemeral_goals = {"find_cheaper", "clarify"}
    if interpretation.turn_goal in ephemeral_goals:
        return []
    for item in interpretation.preference_updates or []:
        if (item.get("type") or "").lower() != "explicit":
            continue
        label = (item.get("label") or "").strip()
        if not label or len(label) < 4:
            continue
        operations.append({
            "op": "ADD",
            "source_type": "explicit",
            "user_confirmed": True,
            "record": {
                "category": item.get("category") or "general",
                "normalized": label,
                "facet": item.get("facet") or "general",
                "value": item.get("value") or label.lower().replace(" ", "_"),
                "scope": "personal",
                "confidence": min(0.95, float(item.get("confidence") or 0.88)),
                "original_user_expression": message[:280],
                "evidence_message_ids": [{"conversation_id": conversation_id, "snippet": message[:180]}],
            },
        })
    if operations:
        return apply_operations(session_id, operations)
    return []


def build_evidence_packet(
    *,
    user_message: str,
    interpretation: TurnInterpretation,
    session_context: dict[str, Any],
    retrieved_taste: dict[str, Any],
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    tool_blocks: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    no_product_explanation: str | None,
    recent_messages: list[dict[str, str]] | None = None,
    ranking_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence_ids: dict[str, dict[str, Any]] = {}
    products_block: list[dict[str, Any]] = []
    for role, product in [("primary", primary)] + [(f"alt_{i}", a) for i, a in enumerate(alternatives[:3])]:
        if not product:
            continue
        ev = build_product_evidence(product)
        review_intel = fetch_review_intelligence(product)
        pid = product.get("id") or role
        entry = {
            "evidence_id": f"product:{pid}",
            "role": role,
            "id": pid,
            "title": product.get("title") or product.get("name"),
            "reference_price": reference_amount(product),
            "rating": product.get("rating"),
            "review_count": product.get("reviewCount"),
            "features": (product.get("sourceFields") or {}).get("features") or [],
            "details": (product.get("sourceFields") or {}).get("details") or {},
            "catalog_facts": [f.get("field") for f in ev.get("facts") or []],
            "review_samples": ev.get("review_samples") or [],
            "review_intel": review_intel,
            "limitations": ev.get("missing") or [],
        }
        products_block.append(entry)
        evidence_ids[entry["evidence_id"]] = entry

    price_facts: list[str] = []
    if comparison and comparison.get("rows"):
        for row in comparison["rows"][:4]:
            if row.get("reference_price") is not None:
                price_facts.append(f"{row.get('title')}: catalog ${float(row['reference_price']):.2f}")
        if comparison.get("price_delta_first_vs_second") is not None:
            delta = comparison["price_delta_first_vs_second"]
            price_facts.append(f"Price delta (first vs second): ${abs(delta):.2f} ({'lower' if delta < 0 else 'higher'} for first)")

    return {
        "user_question": user_message,
        "recent_conversation": (recent_messages or [])[-8:],
        "turn_goal": interpretation.turn_goal,
        "shopping_goal": _goal_summary(interpretation),
        "ranking_reasons": ranking_trace or [],
        "session_context": {
            "devices": session_context.get("devices") or [],
            "requirements": _merged_requirements(session_context, interpretation),
            "category_hint": session_context.get("category_hint"),
            "budget_session": session_context.get("session_budget_max"),
        },
        "my_taste": retrieved_taste,
        "hard_constraints": interpretation.hard_constraints,
        "soft_preferences": interpretation.soft_preferences,
        "products": products_block,
        "comparison_verdict": (comparison or {}).get("verdict"),
        "comparison_rows": (comparison or {}).get("rows"),
        "price_facts": price_facts,
        "limitations": _collect_limitations(products_block, no_product_explanation),
        "clarification_needed": interpretation.clarification_needed,
        "_evidence_index": evidence_ids,
    }


async def compose_grounded_answer(
    packet: dict[str, Any],
    *,
    response_mode: str,
) -> dict[str, Any] | None:
    if not llm_configured():
        return None
    depth = response_mode
    system = (
        "You are Picki, a knowledgeable shopping advisor. Compose a JSON response using ONLY the evidence packet. "
        "Keys: primary_message (string), key_facts (array of {text, evidence_id}), "
        "detail_sections (array of {title, body, evidence_ids}), suggested_actions (array of {label, action}), "
        "optional customer_review_summary, price_value_analysis, product_comparisons (strings). "
        "Every price, spec, and review claim must cite an evidence_id from the packet products. "
        "Do not invent products, stock, certifications, or live prices. "
        "Phrase manufacturer specs as advertised claims, not independent certification. "
        "Avoid filler openers (Great question, Got you) and rigid Verdict/Highlights/Summary templates. "
        "Explain 2-3 meaningful specs and what they mean in real use (e.g. why 4K@120Hz matters for PS5). "
        "Tie pros/cons to the user's stated needs and My Taste when present. "
        "If review evidence is missing, say so briefly instead of inventing sentiment. "
        f"Depth {depth}: QUICK=concise but still specific; STANDARD=actionable research; DEEP=comparisons with trade-offs. "
        "Write naturally; vary structure; no emoji; match user language."
    )
    payload = {k: v for k, v in packet.items() if not k.startswith("_")}
    data = await chat_json(system, json.dumps(payload, ensure_ascii=False)[:14000], timeout=float(
        __import__("os").getenv("PICKI_ANSWER_TIMEOUT", "28")
    ))
    if not data or not (data.get("primary_message") or data.get("message")):
        return None
    msg = (data.get("primary_message") or data.get("message") or "").strip()
    if len(msg) < 8:
        return None
    return {
        "response_mode": depth,
        "primary_message": msg,
        "message": msg,
        "key_facts": _normalize_key_facts(data.get("key_facts")),
        "detail_sections": data.get("detail_sections") or [],
        "suggested_actions": data.get("suggested_actions") or [],
        "customer_review_summary": data.get("customer_review_summary"),
        "price_value_analysis": data.get("price_value_analysis"),
        "product_comparisons": data.get("product_comparisons"),
        "direct_recommendation": None,
        "product_highlights": [],
        "technical_specifications": [],
        "important_drawbacks": [],
        "suggested_follow_up_questions": [],
    }


def validate_grounded_response(
    composed: dict[str, Any],
    packet: dict[str, Any],
    primary: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    index = packet.get("_evidence_index") or {}
    evidence_index = build_product_evidence(primary) if primary else {"facts": []}
    failures.extend(validate_structured_claims(composed, evidence_index))
    failures.extend(_validate_claim_refs(composed, index))
    if failures:
        composed = sanitize_structured(composed, failures)
        composed = _strip_unsupported_prices(composed, index, failures)
    return composed, failures


def assist_response_mode(message: str, interpretation: TurnInterpretation, session_context: dict[str, Any]) -> str:
    depth = (interpretation.response_depth or "").upper()
    if depth in {"QUICK", "STANDARD", "DEEP"}:
        return depth
    return pick_response_mode(message, "message", session_context)


def _interpret_rules(
    message: str,
    *,
    product_id: str | None,
    session_context: dict[str, Any],
    focus_product_ids: list[str],
    shopping_state: Any | None = None,
) -> TurnInterpretation:
    text = (message or "").strip()
    lower = text.lower()
    ctx = session_context or {}
    refs = list(dict.fromkeys([x for x in [product_id, *(focus_product_ids or []), *(ctx.get("focus_product_ids") or [])] if x]))[:4]
    if shopping_state and getattr(shopping_state, "compared_product_ids", None) and re.search(
        r"\bcompare\b|those two|versus|\bvs\.?\b", lower
    ):
        refs = list(dict.fromkeys([*(shopping_state.compared_product_ids or []), *refs]))[:4]
    rule_intent = detect_shopping_intent(text, product_id=product_id, session_context=ctx)
    hard = list(ctx.get("requirements") or [])
    use_cases = []
    if ctx.get("devices"):
        use_cases.append(f"Devices: {', '.join(ctx['devices'])}")
    goal = "general"
    clarification = None
    if re.search(r"\b(save|bookmark|my picks|i('ll| will) (go with|take|get) the first|keep the kabeldirekt)\b|保存|保留.{0,4}清单", lower):
        goal = "save"
    elif re.search(r"\badd( this| that| it)? to (the )?cart|put (it|this) in (the )?cart\b", lower):
        goal = "cart"
    elif re.search(r"\b(cheaper amazon|amazon basics|what about the cheaper|show me something cheaper)\b", lower):
        goal = "compare"
    elif re.search(r"\b(cheaper|less expensive|overpay|affordable|lower price)\b|更便宜|便宜一点|低价", lower):
        goal = "find_cheaper"
    elif re.search(r"\b(why can'?t|normal hdmi|regular hdmi|what'?s different|extra cost|worth it)\b", lower):
        goal = "compare"
    elif re.search(r"\b(which cable should i buy|which one should i (get|buy))\b", lower) and (ctx.get("category_hint") in {"dvi", "hdmi_dvi"} or rule_intent.kind == HDMI_DVI):
        goal = "research"
    elif re.search(r"\bcompare\b|versus|\bvs\.?\b|side by side|which one should i|比较|对比|区别", lower):
        goal = "compare"
    elif re.search(r"\b(older monitor|old monitor|connect.{0,20}monitor)\b", lower) and not re.search(r"\b(hdmi|dvi|vga)\b", lower):
        goal = "clarify"
        clarification = "What connection does the monitor use?"
    elif re.search(r"\b(review|buyers think|dialogue|dialog)\b|评价|评论|购买风险|靠谱吗|可靠", lower):
        goal = "reviews"
    elif re.search(r"\b(will (this|it) work|compatible|compatibility)\b|兼容|适配", lower) and (product_id or refs):
        goal = "compatibility"
    elif re.search(r"\b(budget is|actually,?\s*my budget|make it \$\d+)\b", lower):
        goal = "budget_update"
    elif re.search(r"\b(i usually|care more about|from now on)\b", lower) and not re.search(r"\bneed a|looking for|find\b", lower):
        goal = "preference_update"
    elif re.search(r"\bsimilar\b|alternative|like this|other options", lower):
        goal = "discover_similar"
    elif re.search(r"\b(looking for|need a|help me find|recommend|want something)\b", lower):
        goal = "research"
    elif product_id or refs:
        goal = "research"
    category_kind = rule_intent.kind
    if category_kind == PRODUCT_FOCUS and ctx.get("category_hint") == "hdmi":
        category_kind = HDMI_CABLE
    if category_kind == PRODUCT_FOCUS and ctx.get("category_hint") == "soundbar":
        category_kind = SOUNDBAR
    if goal == "find_cheaper" and ctx.get("category_hint") == "hdmi":
        category_kind = HDMI_CABLE
    if goal == "find_cheaper" and ctx.get("category_hint") == "soundbar":
        category_kind = SOUNDBAR
    if category_kind == SOUNDBAR and goal == "research" and not any("hdmi" in str(x).lower() and "arc" in str(x).lower() for x in hard):
        if not re.search(r"hdmi[\s\-]*arc|optical|bluetooth", lower):
            clarification = "Does your TV have HDMI ARC?"
            goal = "clarify"
    depth = pick_response_mode(text, "message", ctx)
    query = search_query_for_intent(rule_intent, text)
    if goal == "find_cheaper" and category_kind == HDMI_CABLE:
        query = "hdmi cable"
    if category_kind == HDMI_DVI:
        query = "hdmi to dvi"
        if ctx.get("category_hint") not in {"soundbar"}:
            category_kind = HDMI_DVI
    if category_kind == SOUNDBAR:
        query = "soundbar"
    if goal == "find_cheaper" and hard:
        query = search_query_for_intent(
            ShoppingIntent(category_kind, query=query),
            " ".join(hard) + " " + (query or ""),
        )
    return TurnInterpretation(
        turn_goal=goal,
        category_kind=category_kind,
        search_query=query,
        reference_product_ids=refs,
        use_cases=use_cases,
        hard_constraints=hard,
        soft_preferences=[],
        new_requirements=[r for r in hard if r not in (ctx.get("requirements") or [])],
        clarification_needed=clarification,
        response_depth=depth,
        source="rules",
    )


async def _interpret_llm(
    *,
    message: str,
    product_id: str | None,
    session_context: dict[str, Any],
    focus_product_ids: list[str],
    retrieved_taste: dict[str, Any],
    recent_messages: list[dict[str, str]],
    shopping_state: Any | None,
    rule_baseline: TurnInterpretation,
) -> TurnInterpretation | None:
    system = (
        "Understand the shopping turn. Return JSON only with keys: "
        "turn_goal (research|find_cheaper|compare|discover_similar|general|clarify), "
        "category_kind, search_query, reference_product_ids (array), use_cases, hard_constraints, "
        "soft_preferences, new_requirements, clarification_needed (string|null), "
        "preference_updates (array of {type: explicit|session, label, facet, category, confidence}), "
        "removed_constraints (array of strings), conversation_summary (string|null), "
        "response_depth (QUICK|STANDARD|DEEP). "
        "Do not output tool calls. Preserve reference products on vague follow-ups like 'anything cheaper?'. "
        "Session-only budget sensitivity is type session, not explicit. "
        f"category_kind one of: {', '.join(sorted(_CATEGORY_KINDS))}."
    )
    user = json.dumps(
        {
            "message": message,
            "product_id": product_id,
            "focus_product_ids": focus_product_ids,
            "session_context": session_context,
            "retrieved_taste": retrieved_taste,
            "recent_messages": recent_messages[-10:],
            "shopping_state": shopping_state.to_context_patch() if shopping_state and hasattr(shopping_state, "to_context_patch") else None,
            "retrieved_taste": {
                "priority_labels": (retrieved_taste or {}).get("priority_labels"),
                "global": [(i.get("label") or i.get("normalized_preference")) for i in (retrieved_taste or {}).get("global") or []][:4],
            },
            "rule_baseline": {
                "turn_goal": rule_baseline.turn_goal,
                "category_kind": rule_baseline.category_kind,
                "search_query": rule_baseline.search_query,
                "reference_product_ids": rule_baseline.reference_product_ids,
            },
        },
        ensure_ascii=False,
    )
    data = await chat_json(system, user, timeout=float(__import__("os").getenv("PICKI_INTERPRET_TIMEOUT", "20")))
    if not data:
        return None
    return _interpretation_from_payload(data, rule_baseline)


def _interpretation_from_payload(data: dict[str, Any], baseline: TurnInterpretation) -> TurnInterpretation | None:
    goal = (data.get("turn_goal") or baseline.turn_goal or "general").lower().replace("-", "_")
    if goal not in TURN_GOALS:
        goal = baseline.turn_goal
    kind = (data.get("category_kind") or baseline.category_kind or UNKNOWN).lower()
    if kind not in _CATEGORY_KINDS:
        kind = baseline.category_kind
    refs = data.get("reference_product_ids")
    if not isinstance(refs, list) or not refs:
        refs = baseline.reference_product_ids
    refs = [str(x) for x in refs if x][:4]
    depth = (data.get("response_depth") or baseline.response_depth or "STANDARD").upper()
    if depth not in {"QUICK", "STANDARD", "DEEP"}:
        depth = baseline.response_depth
    return TurnInterpretation(
        turn_goal=goal,
        category_kind=kind,
        search_query=data.get("search_query") or baseline.search_query,
        reference_product_ids=refs,
        use_cases=list(data.get("use_cases") or baseline.use_cases),
        hard_constraints=list(data.get("hard_constraints") or baseline.hard_constraints),
        soft_preferences=list(data.get("soft_preferences") or []),
        new_requirements=list(data.get("new_requirements") or []),
        clarification_needed=data.get("clarification_needed"),
        preference_updates=list(data.get("preference_updates") or []),
        removed_constraints=[str(x) for x in (data.get("removed_constraints") or [])],
        conversation_summary=data.get("conversation_summary"),
        response_depth=depth,
        source="llm",
    )


def _merge_interpretation(rule: TurnInterpretation, llm: TurnInterpretation) -> TurnInterpretation:
    goal = llm.turn_goal
    if rule.turn_goal == "find_cheaper":
        goal = "find_cheaper"
    if rule.category_kind in {DISPLAY_MONITOR, HDMI_CABLE, PRODUCT_FOCUS}:
        kind = rule.category_kind
    else:
        kind = llm.category_kind
    refs = llm.reference_product_ids or rule.reference_product_ids
    if rule.reference_product_ids and llm.turn_goal in {"find_cheaper", "compare", "research"}:
        refs = rule.reference_product_ids
    hard = list(dict.fromkeys([*(rule.hard_constraints or []), *(llm.hard_constraints or [])]))
    query = llm.search_query or rule.search_query
    if goal == "find_cheaper" and kind == HDMI_CABLE:
        query = rule.search_query or "hdmi cable"
    return TurnInterpretation(
        turn_goal=goal,
        category_kind=kind,
        search_query=query,
        reference_product_ids=refs,
        use_cases=llm.use_cases or rule.use_cases,
        hard_constraints=hard,
        soft_preferences=llm.soft_preferences,
        new_requirements=llm.new_requirements,
        clarification_needed=llm.clarification_needed,
        preference_updates=llm.preference_updates,
        response_depth=llm.response_depth,
        source="merged",
    )


def _goal_summary(interpretation: TurnInterpretation) -> str:
    parts = [interpretation.turn_goal.replace("_", " ")]
    if interpretation.hard_constraints:
        parts.append("constraints: " + "; ".join(interpretation.hard_constraints[:6]))
    if interpretation.use_cases:
        parts.append("; ".join(interpretation.use_cases[:2]))
    return ". ".join(parts)


def _merged_requirements(session_context: dict[str, Any], interpretation: TurnInterpretation) -> list[str]:
    return list(dict.fromkeys([*(session_context.get("requirements") or []), *(interpretation.hard_constraints or [])]))[:8]


def _collect_limitations(products_block: list[dict[str, Any]], no_product: str | None) -> list[str]:
    lim = []
    if no_product:
        lim.append(no_product)
    for p in products_block:
        lim.extend(p.get("limitations") or [])
    return lim[:8]


def _normalize_key_facts(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:8]:
        if isinstance(item, dict) and item.get("text"):
            out.append({"text": str(item["text"]), "evidence_id": item.get("evidence_id")})
        elif isinstance(item, str):
            out.append({"text": item, "evidence_id": None})
    return out


def _validate_claim_refs(composed: dict[str, Any], index: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if not index:
        return failures
    valid_ids = set(index.keys())
    blob = composed.get("primary_message") or ""
    for fact in composed.get("key_facts") or []:
        eid = fact.get("evidence_id")
        if eid and eid not in valid_ids:
            failures.append(f"Unsupported evidence_id {eid}")
    price_pattern = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
    catalog_prices = {round(float(p["reference_price"]), 2) for p in index.values() if p.get("reference_price") is not None}
    for match in price_pattern.finditer(blob):
        val = round(float(match.group(1)), 2)
        if catalog_prices and val not in catalog_prices and not _price_in_comparison(composed, val):
            failures.append(f"Unsupported price ${val:.2f} in primary_message")
    return failures


def _price_in_comparison(composed: dict[str, Any], val: float) -> bool:
    text = (composed.get("price_value_analysis") or "") + (composed.get("product_comparisons") or "")
    return f"{val:.2f}" in text or f"{val:.0f}" in text


def _strip_unsupported_prices(composed: dict[str, Any], index: dict[str, dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    if not any("price" in f.lower() for f in failures):
        return composed
    composed["price_value_analysis"] = "Prices refer to catalog reference amounts from verified product records only."
    return composed


def fallback_compose(
    *,
    message: str,
    mode: str,
    intent: ShoppingIntent,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    retrieved_taste: dict[str, Any],
    session_context: dict[str, Any],
    no_product_explanation: str | None,
) -> dict[str, Any]:
    return compose_pick_response(
        message=message,
        mode=mode,
        intent=intent,
        primary=primary,
        alternatives=alternatives,
        retrieved_taste=retrieved_taste,
        session_context=session_context,
        no_product_explanation=no_product_explanation,
    )


def no_product_copy(intent: ShoppingIntent) -> str | None:
    if intent.kind == DISPLAY_MONITOR:
        return no_match_message(intent)
    return None
