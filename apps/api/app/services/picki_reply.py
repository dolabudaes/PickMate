from __future__ import annotations

import re
from typing import Any

from .decision_brief import candidate_products, compose_decision_brief, is_decision_moment
from .launch_demo_copy import try_launch_demo_reply
from .product_relevance import DISPLAY_MONITOR, HDMI_CABLE, HDMI_DVI, SOUNDBAR, ShoppingIntent
from .review_provider import fetch_review_intelligence
from .shopping_compare import reference_amount
from .taste_retriever import personalization_profile

DISCOVERY = "DISCOVERY"
CLARIFICATION = "CLARIFICATION"
RECOMMENDATION = "RECOMMENDATION"
COMPARE = "COMPARE"
CHEAPER = "CHEAPER"
BUDGET_UPDATE = "BUDGET_UPDATE"
COMPATIBILITY = "COMPATIBILITY"
REVIEWS = "REVIEWS"
TRADEOFF = "TRADEOFF"
PREFERENCE_UPDATE = "PREFERENCE_UPDATE"
SAVE = "SAVE"
CART = "CART"
NO_MATCH = "NO_MATCH"
OUT_OF_CATALOG = "OUT_OF_CATALOG"
GENERAL_FALLBACK = "GENERAL_FALLBACK"
ACTION_RESULT = "ACTION_RESULT"

SAVE_RE = re.compile(r"\b(save|bookmark|add to my picks|my picks|i('ll| will) (go with|take) the first)\b", re.I)
CART_RE = re.compile(r"\b(add( this| that| it)? to (the )?cart|put (it|this|that) in (the )?cart|cart it)\b", re.I)
CHEAPER_RE = re.compile(r"\b(cheaper|less expensive|overpay|lower[- ]priced|more affordable|too (expensive|pricey))\b", re.I)
COMPARE_RE = re.compile(r"\bcompare\b|versus|\bvs\.?\b|which (one )?(should i|to) (get|buy|pick)|side by side", re.I)
REVIEW_RE = re.compile(r"\b(review|buyers? think|customer feedback|what do (people|buyers)|dialogue|dialog|voices?)\b", re.I)
COMPAT_RE = re.compile(r"\b(will (this|it) work|compatible|compatibility|work with)\b", re.I)
BUDGET_RE = re.compile(r"\b(budget|under|below|less than)\b.*[$€£]?\s*\d+|\bactually,?\s*my budget\b", re.I)
PREF_RE = re.compile(r"\b(i (usually|always|tend to)|care more about|prefer|from now on)\b", re.I)
FIND_RE = re.compile(r"\b(looking for|need a|help me find|recommend|show me|want something|find me)\b", re.I)
WHY_RE = re.compile(r"\b(why this|trade-?off|difference|better for)\b", re.I)
BANNED = re.compile(
    r"based on your stated preferences|here are the top 3|according to my analysis|"
    r"as an ai shopping assistant|i recommend considering the following|"
    r"would you like me to provide further|your preference profile indicates|"
    r"understanding your needs|my recommendations|next steps",
    re.I,
)


def classify_reply_type(
    *,
    message: str,
    action: str,
    intent: ShoppingIntent,
    interpretation: Any | None,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    no_product_explanation: str | None,
    action_status: dict[str, Any] | None = None,
) -> str:
    if action_status:
        return ACTION_RESULT
    text = (message or "").strip()
    lower = text.lower()
    goal = getattr(interpretation, "turn_goal", None) if interpretation else None
    if re.search(r"\b(older monitor|old monitor|connect.{0,20}monitor|laptop.{0,12}monitor)\b", lower) and not re.search(r"\b(hdmi|dvi|vga)\b", lower):
        return CLARIFICATION
    if intent.kind == HDMI_DVI and not primary and goal == "clarify":
        return CLARIFICATION
    if no_product_explanation and intent.kind == DISPLAY_MONITOR:
        return OUT_OF_CATALOG
    if action == "cheaper" or goal == "find_cheaper" or CHEAPER_RE.search(lower):
        return CHEAPER
    if no_product_explanation or (not primary and goal not in {"clarify", "save", "cart", "preference_update", "find_cheaper"}):
        if FIND_RE.search(text) or goal in {"research", "discover_similar"}:
            return NO_MATCH
        if not text:
            return GENERAL_FALLBACK
    if action == "compare" or goal == "compare" or COMPARE_RE.search(lower):
        return COMPARE
    if SAVE_RE.search(lower) or goal == "save":
        return SAVE
    if CART_RE.search(lower) or goal == "cart":
        return CART
    if getattr(interpretation, "clarification_needed", None) and not primary:
        return CLARIFICATION
    if goal == "budget_update" or (BUDGET_RE.search(lower) and re.search(r"\d", lower) and not FIND_RE.search(lower)):
        return BUDGET_UPDATE
    if goal == "preference_update" or (PREF_RE.search(lower) and not FIND_RE.search(lower) and not CHEAPER_RE.search(lower)):
        return PREFERENCE_UPDATE
    if COMPAT_RE.search(lower) and (primary or "hdmi arc" in lower or "work" in lower):
        return COMPATIBILITY
    if REVIEW_RE.search(lower) or goal == "reviews":
        return REVIEWS
    if WHY_RE.search(lower) or action == "why_this":
        return TRADEOFF
    if primary and (FIND_RE.search(lower) or goal in {"research", "discover_similar", "general"}):
        return RECOMMENDATION
    if primary:
        return RECOMMENDATION
    if FIND_RE.search(lower):
        return DISCOVERY
    return GENERAL_FALLBACK


def compose_natural_reply(
    *,
    reply_type: str,
    message: str,
    intent: ShoppingIntent,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    retrieved_taste: dict[str, Any],
    session_context: dict[str, Any],
    interpretation: Any | None = None,
    no_product_explanation: str | None = None,
    action_status: dict[str, Any] | None = None,
    comparison_products: list[dict[str, Any]] | None = None,
    mode: str = "QUICK",
) -> dict[str, Any]:
    profile = personalization_profile(retrieved_taste)
    builders = {
        DISCOVERY: _discovery,
        CLARIFICATION: _clarification,
        RECOMMENDATION: _recommendation,
        COMPARE: _compare,
        CHEAPER: _cheaper,
        BUDGET_UPDATE: _budget_update,
        COMPATIBILITY: _compatibility,
        REVIEWS: _reviews,
        TRADEOFF: _tradeoff,
        PREFERENCE_UPDATE: _preference,
        SAVE: _save,
        CART: _cart,
        NO_MATCH: _no_match,
        OUT_OF_CATALOG: _out_of_catalog,
        ACTION_RESULT: _action_result,
        GENERAL_FALLBACK: _fallback,
    }
    demo = try_launch_demo_reply(
        message=message,
        primary=primary,
        alternatives=alternatives,
        comparison_products=comparison_products or [],
        action_status=action_status,
        session_context=session_context,
        retrieved_taste=retrieved_taste,
        memory_enabled=session_context.get("memory_enabled", True),
    )
    if demo:
        return {**demo, "response_mode": mode if mode in {"QUICK", "STANDARD", "DEEP"} else demo.get("response_mode") or "QUICK"}
    builder = builders.get(reply_type, _fallback)
    payload = builder(
        message=message,
        intent=intent,
        primary=primary,
        alternatives=alternatives,
        profile=profile,
        session_context=session_context,
        interpretation=interpretation,
        no_product_explanation=no_product_explanation,
        action_status=action_status,
        comparison_products=comparison_products or [],
        retrieved_taste=retrieved_taste,
    )
    pair = candidate_products(primary, alternatives, comparison_products or [], session_context)
    if not payload.get("decision_brief") and is_decision_moment(message, reply_type, pair):
        brief = compose_decision_brief(
            message=message,
            products=pair,
            shopping_context=session_context,
            retrieved_taste=retrieved_taste,
            memory_enabled=session_context.get("memory_enabled", True),
            reply_type=reply_type,
        )
        if brief:
            payload = {**payload, **brief}
    text = _clean_copy(payload.get("primary_message") or "")
    refs = payload.get("product_refs")
    if refs is None:
        refs = _product_refs(primary, alternatives, reply_type)
    actions = payload.get("suggested_actions")
    if actions is None:
        actions = _default_actions(reply_type, intent, primary, alternatives)
    return {
        "response_mode": mode if mode in {"QUICK", "STANDARD", "DEEP"} else "QUICK",
        "response_type": payload.get("response_type") or reply_type,
        "primary_message": text,
        "message": text,
        "key_facts": payload.get("key_facts") or [],
        "product_refs": refs,
        "detail_sections": payload.get("detail_sections") or [],
        "suggested_actions": actions[:3],
        "direct_recommendation": payload.get("direct_recommendation"),
        "product_highlights": [],
        "technical_specifications": [],
        "price_value_analysis": payload.get("price_value_analysis"),
        "customer_review_summary": payload.get("customer_review_summary"),
        "product_comparisons": payload.get("product_comparisons"),
        "important_drawbacks": payload.get("important_drawbacks") or [],
        "suggested_follow_up_questions": [a["label"] for a in actions[:3]],
        "comparison_data": payload.get("comparison_data"),
        "clarification_options": payload.get("clarification_options") or [],
        "decision_highlight": payload.get("decision_highlight"),
        "evidence_status": payload.get("evidence_status") or "catalog",
        "decision_brief": payload.get("decision_brief"),
    }


def _clean_copy(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = BANNED.sub("", text)
    text = re.sub(r"\b(Got it!|Great choice!|Absolutely!)\s*", "", text)
    return text.strip()


def _short_title(product: dict[str, Any] | None) -> str:
    if not product:
        return "this one"
    name = (product.get("name") or "").strip()
    brand = (product.get("brand") or "").strip()
    if brand and name.lower().startswith(brand.lower()):
        name = name[len(brand) :].strip(" -–—")
    return (name[:64] if len(name) > 64 else name) or "this product"


def _price(product: dict[str, Any] | None) -> float | None:
    return reference_amount(product) if product else None


def _money(amount: float | None) -> str:
    if amount is None:
        return "Not listed"
    if abs(amount - round(amount)) < 0.001:
        return f"${amount:.0f}"
    return f"${amount:.2f}"


def _blob(product: dict[str, Any] | None) -> str:
    if not product:
        return ""
    source = product.get("sourceFields") or {}
    parts = [
        product.get("name") or "",
        " ".join(source.get("features") or []),
        " ".join(f"{k} {v}" for k, v in (source.get("details") or {}).items()),
    ]
    return " ".join(parts).lower()


def _spec_reason(product: dict[str, Any], session_context: dict[str, Any]) -> str:
    blob = _blob(product)
    reqs = " ".join(session_context.get("requirements") or []).lower()
    source = product.get("sourceFields") or {}
    features = [str(x) for x in (source.get("features") or []) if x]
    if "hdmi" in reqs and "arc" in reqs:
        if re.search(r"hdmi[\s\-]*arc", blob):
            return "HDMI ARC is listed in the connection specs."
        return "It stays under your budget in the current catalog."
    if "4k" in reqs and "120" in reqs:
        if re.search(r"4k.*120|120\s*hz|48\s*gbps|hdmi\s*2\.1", blob):
            return "The listing mentions 4K / high-refresh HDMI capability."
        return "Confirm 120Hz support on the manufacturer page before buying."
    if "dialogue" in " ".join(session_context.get("use_cases") or []).lower() or "dialog" in blob:
        if re.search(r"dialogu?e|speech|voice", blob):
            return "The listing mentions dialogue or speech clarity."
    for feature in features:
        if len(feature) > 18:
            return feature[:110].rstrip(".") + "."
    price = _price(product)
    if price is not None:
        return f"Catalog price is {_money(price)}."
    return "Verified from the catalog listing."


def _hdmi_arc_status(product: dict[str, Any] | None) -> str:
    if not product:
        return "unknown"
    blob = _blob(product)
    if re.search(r"hdmi[\s\-]*arc", blob):
        return "supported"
    details = " ".join(str(v) for v in ((product.get("sourceFields") or {}).get("details") or {}).values()).lower()
    if "hdmi" in blob and "arc" not in blob and details and "input" in details:
        return "unsupported"
    if "hdmi" in blob and "arc" not in blob:
        return "unknown"
    return "unknown"


def _product_refs(primary: dict[str, Any] | None, alternatives: list[dict[str, Any]], reply_type: str) -> list[dict[str, Any]]:
    if reply_type in {CLARIFICATION, GENERAL_FALLBACK, ACTION_RESULT, OUT_OF_CATALOG} and not primary:
        return []
    refs: list[dict[str, Any]] = []
    if primary:
        refs.append(_ref_row(primary, "primary", None))
    extra = alternatives[:2] if reply_type in {RECOMMENDATION, CHEAPER, COMPARE, NO_MATCH} else alternatives[:1]
    for alt in extra:
        if alt.get("id") and alt.get("id") != (primary or {}).get("id"):
            refs.append(_ref_row(alt, "alternative", None))
    return refs[:3]


def _ref_row(product: dict[str, Any], role: str, reason: str | None) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    feature = (source.get("features") or [None])[0]
    return {
        "product_id": product.get("id"),
        "role": role,
        "title": _short_title(product),
        "brand": product.get("brand"),
        "price": _price(product),
        "spec_line": reason or (str(feature)[:110] if feature else None),
    }


def _default_actions(reply_type: str, intent: ShoppingIntent, primary: dict[str, Any] | None, alternatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if reply_type in {OUT_OF_CATALOG}:
        return [
            {"id": "audio-setup", "label": "Gaming TV audio", "kind": "message", "message": "Help me find a gaming TV soundbar under $200."},
            {"id": "hdmi-cables", "label": "HDMI cables", "kind": "message", "message": "Show me HDMI cables under $15."},
        ]
    if not primary:
        return [
            {"id": "set-budget", "label": "Add a budget", "kind": "message", "message": "My budget is no more than $150."},
            {"id": "find-soundbar", "label": "Find a soundbar", "kind": "message", "message": "I need a TV soundbar under $200."},
        ]
    if reply_type == COMPARE:
        return [
            {"id": "cheaper", "label": "Find a cheaper option", "kind": "quick", "action": "cheaper"},
            {"id": "save", "label": "Save this choice", "kind": "message", "message": "Save the product you recommend to My Picks."},
        ]
    if reply_type == CHEAPER:
        return [
            {"id": "compare", "label": "Compare with the first", "kind": "message", "message": "Compare this with the first product."},
            {"id": "reviews", "label": "View review evidence", "kind": "message", "message": "What strengths and risks are supported by verified reviews?"},
        ]
    return [
        {"id": "cheaper", "label": "Is there a cheaper option?", "kind": "quick", "action": "cheaper"},
        {"id": "reviews", "label": "View review evidence", "kind": "message", "message": "What strengths and risks are supported by verified reviews?"},
        {"id": "compare", "label": "Compare products", "kind": "quick", "action": "compare"},
    ]


def _discovery(**kw: Any) -> dict[str, Any]:
    clarification = _maybe_clarify(kw["message"], kw["intent"], kw["session_context"], kw.get("interpretation"))
    if clarification:
        return clarification
    if kw.get("primary"):
        return _recommendation(**kw)
    return {
        "primary_message": "I can help narrow that down. What matters most — budget, connections, or how you'll use it?",
        "clarification_options": [
            {"id": "budget", "label": "Budget", "message": "My budget is under $150"},
            {"id": "hdmi", "label": "HDMI ARC", "message": "My TV has HDMI ARC."},
            {"id": "use", "label": "Everyday TV", "message": "This is mainly for everyday TV."},
        ],
        "product_refs": [],
    }


def _maybe_clarify(message: str, intent: ShoppingIntent, session_context: dict[str, Any], interpretation: Any) -> dict[str, Any] | None:
    needed = getattr(interpretation, "clarification_needed", None) if interpretation else None
    reqs = [str(x).lower() for x in (session_context.get("requirements") or [])]
    use_cases = [str(x).lower() for x in (session_context.get("use_cases") or [])]
    if intent.kind == SOUNDBAR and not any("hdmi" in r and "arc" in r for r in reqs):
        if not needed:
            needed = "connection"
        return {
            "primary_message": "I can stay under that budget. Does your TV have HDMI ARC, or would optical or Bluetooth work?",
            "clarification_options": [
                {"id": "hdmi-arc", "label": "HDMI ARC", "message": "My TV has HDMI ARC."},
                {"id": "optical", "label": "Optical", "message": "I need an optical connection."},
                {"id": "bluetooth", "label": "Bluetooth", "message": "Bluetooth is fine."},
            ],
            "product_refs": [],
            "evidence_status": "needs_input",
        }
    if intent.kind == SOUNDBAR and not use_cases and "tv" not in (message or "").lower():
        return {
            "primary_message": "I can help narrow that down. Is this mainly for movies, everyday TV, or music?",
            "clarification_options": [
                {"id": "movies", "label": "Movies", "message": "This is mainly for movies."},
                {"id": "tv", "label": "Everyday TV", "message": "This is mainly for everyday TV."},
                {"id": "music", "label": "Music", "message": "This is mainly for music."},
            ],
            "product_refs": [],
            "evidence_status": "needs_input",
        }
    if needed:
        return {
            "primary_message": str(needed),
            "clarification_options": [],
            "product_refs": [],
        }
    return None


def _clarification(**kw: Any) -> dict[str, Any]:
    return _maybe_clarify(kw["message"], kw["intent"], kw["session_context"], kw.get("interpretation")) or {
        "primary_message": "Which product do you mean — the first one, or the one we just looked at?",
        "clarification_options": [
            {"id": "first", "label": "The first one", "message": "the first one"},
            {"id": "this", "label": "This one", "message": "this one"},
        ],
        "product_refs": [],
    }


def _recommendation(**kw: Any) -> dict[str, Any]:
    primary = kw.get("primary")
    if not primary:
        return _no_match(**kw)
    alts = kw.get("alternatives") or []
    reason = _spec_reason(primary, kw["session_context"])
    budget = kw["session_context"].get("session_budget_max")
    opener = "I'd start with these." if alts else "This is the strongest match I can verify."
    if any("hdmi" in str(r).lower() and "arc" in str(r).lower() for r in (kw["session_context"].get("requirements") or [])):
        opener = "I'd prioritize HDMI ARC compatibility and stay within your budget."
        if alts:
            opener += " These are the strongest matches I can verify."
        else:
            opener += " This is the strongest match I can verify."
    elif budget:
        opener = f"Staying under {_money(float(budget))}. {opener}"
    refs = [_ref_row(primary, "primary", reason)]
    for alt in alts[:2]:
        refs.append(_ref_row(alt, "alternative", _spec_reason(alt, kw["session_context"])))
    return {
        "primary_message": opener,
        "product_refs": refs,
        "key_facts": [{"text": reason}],
        "direct_recommendation": _short_title(primary),
    }


def _cheaper(**kw: Any) -> dict[str, Any]:
    primary = kw.get("primary")
    alts = kw.get("alternatives") or []
    ctx = kw["session_context"]
    if not primary:
        if kw.get("intent") and kw["intent"].kind == HDMI_DVI:
            return {
                "primary_message": "I couldn't find a cheaper HDMI-to-DVI option that still matches your setup. I'd keep this one rather than switch to an incompatible cable.",
                "product_refs": [],
                "suggested_actions": [
                    {"id": "compatibility", "label": "Check compatibility", "kind": "message", "message": "Check the connector compatibility again."},
                    {"id": "reviews", "label": "Read reviews", "kind": "message", "message": "What about buyer reviews?"},
                ],
                "evidence_status": "no_cheaper_match",
            }
        return {
            "primary_message": "I couldn't find a cheaper option that keeps all your requirements. Want to widen the budget or review which features are essential?",
            "product_refs": [],
            "suggested_actions": [
                {"id": "widen", "label": "Widen the budget", "kind": "message", "message": "Actually, my budget is $250."},
                {"id": "keep", "label": "Keep current requirements", "kind": "message", "message": "Keep everything else the same."},
            ],
            "evidence_status": "no_cheaper_match",
        }
    trade = _verified_tradeoff(ctx.get("_previous_product"), primary)
    if trade:
        line = f"Here's a lower-priced option. The trade-off is {trade}."
    else:
        line = "This one costs less and still meets your required specs."
    refs = [_ref_row(primary, "primary", _spec_reason(primary, ctx))]
    for alt in alts[:1]:
        refs.append(_ref_row(alt, "alternative", _spec_reason(alt, ctx)))
    return {"primary_message": line, "product_refs": refs, "key_facts": [{"text": line}]}


def _verified_tradeoff(previous: dict[str, Any] | None, chosen: dict[str, Any] | None) -> str | None:
    if not previous or not chosen or previous.get("id") == chosen.get("id"):
        return None
    left = _price(previous)
    right = _price(chosen)
    diffs: list[str] = []
    prev_blob = _blob(previous)
    new_blob = _blob(chosen)
    if re.search(r"hdmi[\s\-]*arc", prev_blob) and not re.search(r"hdmi[\s\-]*arc", new_blob):
        return None
    if "3.1" in prev_blob and "3.1" not in new_blob and ("2.0" in new_blob or "2.1" in new_blob):
        diffs.append("fewer listed channels")
    if left is not None and right is not None and right < left:
        brand_a = (previous.get("brand") or "").lower()
        brand_b = (chosen.get("brand") or "").lower()
        if brand_a and brand_b and brand_a != brand_b:
            diffs.append("a different brand")
    if "wireless subwoofer" in prev_blob and "wireless subwoofer" not in new_blob:
        diffs.append("no listed wireless subwoofer")
    return diffs[0] if diffs else None


def _compare(**kw: Any) -> dict[str, Any]:
    products = [p for p in (kw.get("comparison_products") or []) if p]
    primary = kw.get("primary")
    alts = kw.get("alternatives") or []
    if len(products) < 2:
        products = [p for p in [primary, *alts] if p][:2]
    if len(products) < 2:
        return {
            "primary_message": "I only have one product in view. Tell me which other one to compare.",
            "product_refs": _product_refs(primary, [], COMPARE),
        }
    left, right = products[0], products[1]
    winner = _compare_winner(left, right, kw["session_context"])
    reason = _compare_reason(winner, left, right, kw["session_context"])
    data = _comparison_data(left, right, winner)
    return {
        "primary_message": f"I'd lean toward {_short_title(winner)} for your setup. {reason}",
        "product_refs": [_ref_row(left, "compare_a", None), _ref_row(right, "compare_b", None)],
        "comparison_data": data,
        "product_comparisons": data.get("summary"),
        "direct_recommendation": _short_title(winner),
        "detail_sections": [{"id": "compare-specs", "title": "Listed specs", "collapsed": True, "lines": data.get("extra_lines") or []}],
    }


def _compare_winner(left: dict[str, Any], right: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    reqs = " ".join(ctx.get("requirements") or []).lower()
    if "hdmi" in reqs and "arc" in reqs:
        left_arc = _hdmi_arc_status(left) == "supported"
        right_arc = _hdmi_arc_status(right) == "supported"
        if left_arc and not right_arc:
            return left
        if right_arc and not left_arc:
            return right
    lp, rp = _price(left), _price(right)
    if lp is not None and rp is not None and lp != rp:
        return left if lp < rp else right
    return left


def _compare_reason(winner: dict[str, Any], left: dict[str, Any], right: dict[str, Any], ctx: dict[str, Any]) -> str:
    other = right if winner.get("id") == left.get("id") else left
    wp, op = _price(winner), _price(other)
    if _hdmi_arc_status(winner) == "supported" and any("arc" in str(r).lower() for r in (ctx.get("requirements") or [])):
        if wp is not None and op is not None and wp < op:
            return "It lists HDMI ARC and costs less."
        return "HDMI ARC is listed in its connection specs."
    if wp is not None and op is not None and wp < op:
        return f"It's {_money(op - wp)} less in the catalog."
    return "The listed specs line up more closely with what you asked for."


def _comparison_data(left: dict[str, Any], right: dict[str, Any], winner: dict[str, Any]) -> dict[str, Any]:
    fields = [
        ("Price", _money(_price(left)), _money(_price(right))),
        ("HDMI ARC", _arc_label(left), _arc_label(right)),
        ("Channels", _channel_label(left), _channel_label(right)),
    ]
    extra = []
    for product, tag in ((left, "A"), (right, "B")):
        source = product.get("sourceFields") or {}
        details = source.get("details") or {}
        dims = details.get("Product Dimensions") or details.get("Item Dimensions")
        if dims:
            extra.append(f"{tag} dimensions: {dims}")
    return {
        "winner_product_id": winner.get("id"),
        "columns": [
            {"product_id": left.get("id"), "title": _short_title(left), "price": _price(left)},
            {"product_id": right.get("id"), "title": _short_title(right), "price": _price(right)},
        ],
        "rows": [{"label": label, "values": [a, b]} for label, a, b in fields],
        "summary": f"{_short_title(winner)} is the closer fit from verified listing data.",
        "extra_lines": extra,
    }


def _arc_label(product: dict[str, Any]) -> str:
    status = _hdmi_arc_status(product)
    if status == "supported":
        return "Listed"
    if status == "unsupported":
        return "Not listed"
    return "Not listed"


def _channel_label(product: dict[str, Any]) -> str:
    match = re.search(r"(\d\.\d)\s*-?\s*channel", _blob(product), re.I)
    return match.group(1) if match else "Not listed"


def _budget_update(**kw: Any) -> dict[str, Any]:
    budget = kw["session_context"].get("session_budget_max")
    cap = _money(float(budget)) if budget else "your new budget"
    if kw.get("primary"):
        rec = _recommendation(**kw)
        rec["primary_message"] = f"Under {cap} — I'll keep the rest of your requirements the same. {rec['primary_message']}"
        rec["decision_highlight"] = f"Budget updated to {cap}"
        return rec
    return {
        "primary_message": f"Under {cap} — I'll keep the rest of your requirements the same.",
        "decision_highlight": f"Budget updated to {cap}",
        "product_refs": [],
    }


def _compatibility(**kw: Any) -> dict[str, Any]:
    primary = kw.get("primary")
    alts = kw.get("alternatives") or []
    status = _hdmi_arc_status(primary)
    if status == "supported":
        return {
            "primary_message": "Yes — HDMI ARC is listed in its connection specs.",
            "product_refs": _product_refs(primary, [], COMPATIBILITY),
            "evidence_status": "verified",
        }
    if status == "unsupported":
        alt = next((item for item in alts if _hdmi_arc_status(item) == "supported"), None)
        extra = " Here's an alternative that does." if alt else ""
        refs = _product_refs(alt or primary, [primary] if alt else [], COMPATIBILITY)
        return {
            "primary_message": f"No — this model doesn't list HDMI ARC support.{extra}",
            "product_refs": refs,
            "evidence_status": "verified_negative",
        }
    return {
        "primary_message": "I can't confirm HDMI ARC support from the available specs. I'd check the manufacturer's connection details before buying.",
        "product_refs": _product_refs(primary, [], COMPATIBILITY),
        "evidence_status": "insufficient",
    }


def _reviews(**kw: Any) -> dict[str, Any]:
    primary = kw.get("primary")
    if not primary:
        return {"primary_message": "I don't have a product in view to pull reviews from.", "product_refs": []}
    intel = fetch_review_intelligence(primary)
    blob = _blob(primary)
    dialogue = bool(re.search(r"dialogu?e|speech|voice|clarify", blob))
    if "dialogue" in (kw["message"] or "").lower() or "dialog" in (kw["message"] or "").lower():
        if dialogue:
            return {
                "primary_message": "The listing mentions dialogue or speech clarity. I can't independently verify how it sounds.",
                "product_refs": _product_refs(primary, kw.get("alternatives") or [], REVIEWS),
                "customer_review_summary": intel.get("summary") if intel.get("available") else None,
                "detail_sections": _review_section(intel),
                "evidence_status": "manufacturer_claim",
            }
        return {
            "primary_message": "I couldn't verify dialogue performance from the available specs or reviews.",
            "product_refs": _product_refs(primary, [], REVIEWS),
            "detail_sections": _review_section(intel),
            "evidence_status": "insufficient",
        }
    if intel.get("available") and (intel.get("sources") or intel.get("positives")):
        snippet = ""
        if intel.get("positives"):
            snippet = str(intel["positives"][0])
        elif intel.get("sources"):
            snippet = str((intel["sources"][0] or {}).get("snippet") or "")
        caveat = ""
        if intel.get("complaints"):
            caveat = f" {str(intel['complaints'][0])[:90]}."
        if snippet:
            return {
                "primary_message": f"Buyers frequently mention {snippet[:110].rstrip('.')}.{caveat}".strip(),
                "product_refs": _product_refs(primary, [], REVIEWS),
                "customer_review_summary": intel.get("summary"),
                "detail_sections": _review_section(intel),
                "evidence_status": "reviews",
            }
    return {
        "primary_message": "I don't have enough review data to call that confidently. I can still compare the verified specs.",
        "product_refs": _product_refs(primary, kw.get("alternatives") or [], REVIEWS),
        "evidence_status": "insufficient",
        "suggested_actions": [
            {"id": "compare", "label": "Compare specs", "kind": "quick", "action": "compare"},
            {"id": "cheaper", "label": "Find cheaper", "kind": "quick", "action": "cheaper"},
        ],
    }


def _review_section(intel: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[str] = []
    if intel.get("summary"):
        lines.append(str(intel["summary"]))
    for item in intel.get("sources") or []:
        snippet = item.get("snippet")
        if snippet:
            lines.append(str(snippet)[:200])
    if not lines:
        return []
    return [{"id": "reviews", "title": "Review excerpts", "collapsed": True, "lines": lines[:5]}]


def _tradeoff(**kw: Any) -> dict[str, Any]:
    primary = kw.get("primary")
    alts = kw.get("alternatives") or []
    if primary and alts:
        trade = _verified_tradeoff(primary, alts[0])
        if trade:
            return {
                "primary_message": f"The main difference is {trade}. I'd keep {_short_title(primary)} unless that matters more.",
                "product_refs": _product_refs(primary, alts, TRADEOFF),
            }
    if primary:
        return {
            "primary_message": _spec_reason(primary, kw["session_context"]),
            "product_refs": _product_refs(primary, alts, TRADEOFF),
        }
    return _fallback(**kw)


def _preference(**kw: Any) -> dict[str, Any]:
    labels = []
    taste = kw.get("retrieved_taste") or {}
    for item in (taste.get("global") or [])[:3]:
        label = item.get("normalized_preference") or item.get("label")
        if label:
            labels.append(label)
    if any("value" in str(x).lower() for x in labels):
        line = "I'll prioritize value over brand when comparing suitable products."
    elif any("compat" in str(x).lower() for x in labels):
        line = "I'll prioritize compatibility first, then price, when comparing products for you."
    else:
        line = "I'll keep that in mind when comparing suitable products."
    extra = _recommendation(**kw) if kw.get("primary") else {"product_refs": []}
    extra["primary_message"] = line
    extra["decision_highlight"] = "My Taste updated"
    return extra


def _save(**kw: Any) -> dict[str, Any]:
    status = kw.get("action_status") or {}
    if status.get("saved"):
        return {
            "primary_message": "Saved to My Picks.",
            "decision_highlight": "Saved to My Picks",
            "product_refs": _product_refs(kw.get("primary"), [], SAVE),
            "suggested_actions": [],
        }
    if status.get("ambiguous"):
        return _clarification(**kw)
    return {
        "primary_message": "I could not save that yet. Tell me which product you mean.",
        "product_refs": _product_refs(kw.get("primary"), kw.get("alternatives") or [], SAVE),
    }


def _cart(**kw: Any) -> dict[str, Any]:
    status = kw.get("action_status") or {}
    if status.get("saved"):
        return {
            "primary_message": "Added to My Picks.",
            "decision_highlight": "Added to My Picks",
            "product_refs": _product_refs(kw.get("primary"), [], CART),
            "suggested_actions": [],
        }
    return {
        "primary_message": "I could not add that yet. Tell me which product you mean.",
        "product_refs": _product_refs(kw.get("primary"), kw.get("alternatives") or [], CART),
    }


def _action_result(**kw: Any) -> dict[str, Any]:
    status = kw.get("action_status") or {}
    if status.get("kind") == "save":
        return _save(**kw)
    if status.get("kind") == "cart":
        return _cart(**kw)
    return {"primary_message": status.get("message") or "Done.", "decision_highlight": status.get("message"), "product_refs": _product_refs(kw.get("primary"), [], ACTION_RESULT)}


def _no_match(**kw: Any) -> dict[str, Any]:
    text = kw.get("no_product_explanation") or "Nothing in the current catalog meets all of those requirements."
    if kw["intent"].kind == SOUNDBAR:
        text = "Nothing in the current catalog meets all of those requirements. I can widen the budget or drop a connection constraint."
    return {
        "primary_message": text,
        "product_refs": [],
        "suggested_actions": [
            {"id": "widen", "label": "Widen the budget", "kind": "message", "message": "Actually, my budget is $300."},
            {"id": "relax", "label": "Drop HDMI ARC", "kind": "message", "message": "I no longer need HDMI ARC."},
        ],
        "evidence_status": "no_match",
    }


def _out_of_catalog(**kw: Any) -> dict[str, Any]:
    return {
        "primary_message": "I don't have gaming monitors in this catalog, so I can't recommend one reliably. I can help with audio for a gaming setup, though.",
        "product_refs": [],
        "evidence_status": "out_of_catalog",
        "suggested_actions": [
            {"id": "audio-setup", "label": "Audio for a gaming setup", "kind": "message", "message": "Help me find a soundbar for a gaming TV under $200"},
            {"id": "hdmi-cables", "label": "HDMI cables", "kind": "message", "message": "Show HDMI cables under $15"},
        ],
    }


def _fallback(**kw: Any) -> dict[str, Any]:
    if kw.get("primary"):
        return _recommendation(**kw)
    return {
        "primary_message": "Tell me what you're shopping for — a product type, budget, or a must-have connection.",
        "product_refs": [],
        "suggested_actions": [
            {"id": "soundbar", "label": "Soundbar under $200", "kind": "message", "message": "I need a soundbar for my TV under $200."},
            {"id": "hdmi", "label": "HDMI cable", "kind": "message", "message": "I need an HDMI cable for my PS5."},
        ],
    }
