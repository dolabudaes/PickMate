from __future__ import annotations

import re
from typing import Any

from .review_provider import fetch_review_intelligence
from .shopping_compare import (
    BASICS_ID,
    DVI_ID,
    KABEL_ID,
    _compat_first,
    _needs_120,
    _needs_60,
    _needs_dvi,
    _taste_labels,
    _wants_value,
    connector_kind,
    explain_comparison,
    listed_refresh,
    listed_video,
    product_kind,
    reference_amount,
    short_name,
)

DECISION_RE = re.compile(
    r"which (cable|one) should i buy|so which cable|should i buy|"
    r"worth it|extra cost|cheaper amazon|"
    r"why can'?t|normal hdmi|regular hdmi|"
    r"planning a 120|staying at 60|prioritize lower price",
    re.I,
)

SWITCHES = (
    {"id": "upgrade_120", "label": "Planning a 120Hz upgrade", "message": "I am planning to upgrade to 120Hz."},
    {"id": "stay_60", "label": "Staying at 60Hz", "message": "I will stay at 60Hz."},
    {"id": "lower_price", "label": "Prioritize a lower price", "message": "After the requirements are met, prioritize a lower price."},
)


def is_decision_moment(message: str, reply_type: str | None = None, products: list[dict[str, Any]] | None = None) -> bool:
    if reply_type in {"CLARIFICATION", "PREFERENCE_UPDATE", "ACTION_RESULT", "DISCOVERY", "GENERAL_FALLBACK", "REVIEWS"}:
        return False
    kinds = {product_kind(item) for item in (products or []) if item}
    hdmi = bool(kinds) and kinds <= {"hdmi_cable", "hdmi_dvi"}
    if DECISION_RE.search(message or ""):
        return not kinds or hdmi
    if reply_type == "COMPARE" and hdmi:
        return True
    return False


def compose_decision_brief(
    *,
    message: str,
    products: list[dict[str, Any]],
    shopping_context: dict[str, Any] | None = None,
    retrieved_taste: dict[str, Any] | list[str] | None = None,
    memory_enabled: bool = True,
    reply_type: str = "COMPARE",
) -> dict[str, Any] | None:
    candidates = [item for item in products if item and item.get("id")]
    if len(candidates) < 1:
        return None
    context = dict(shopping_context or {})
    labels = _taste_labels(retrieved_taste) if memory_enabled else []
    explained = explain_comparison(
        candidates,
        shopping_context=context,
        retrieved_taste=retrieved_taste if memory_enabled else [],
        memory_enabled=memory_enabled,
    )
    winner_id = explained.get("winner_product_id")
    winner = next((item for item in candidates if item.get("id") == winner_id), None)
    others = [item for item in candidates if item.get("id") != winner_id]
    loser = others[0] if others else None
    evidence = _collect_evidence(candidates, context)
    reviews = _review_bundle(candidates, context)
    taste_used = _taste_actually_used(explained, labels, memory_enabled, context, winner)
    take = _compose_take(
        message=message,
        winner=winner,
        loser=loser,
        context=context,
        explained=explained,
        reviews=reviews,
        taste_used=taste_used,
        labels=labels,
    )
    angles = _angles(winner, loser, context, reviews, taste_used, labels)
    gap = reviews.get("gap") if not reviews.get("available") else None
    refs = [_ref(item, "primary" if winner and item.get("id") == winner.get("id") else "alternative") for item in candidates[:2]]
    comparison = _comparison_data(candidates[:2], winner_id) if len(candidates) >= 2 else None
    change = _change_condition(context, winner, loser)
    actions = _actions(winner, loser)
    return {
        "response_type": reply_type if reply_type not in {None, "GENERAL_FALLBACK"} else "DECISION_BRIEF",
        "primary_message": take,
        "message": take,
        "product_refs": refs,
        "comparison_data": comparison,
        "suggested_actions": actions,
        "direct_recommendation": refs[0]["title"] if refs else None,
        "decision_brief": {
            "angles": angles,
            "review": {
                "available": bool(reviews.get("available")),
                "lines": reviews.get("lines") or [],
                "quotes": reviews.get("quotes") or [],
            } if reviews.get("available") or reviews.get("gap") else None,
            "gap": gap,
            "change_condition": change,
            "switches": list(SWITCHES),
            "evidence": evidence,
            "winner_product_id": winner_id,
        },
        "key_facts": [],
        "detail_sections": [],
        "decision_highlight": None,
        "evidence_status": "catalog",
        "customer_review_summary": (reviews.get("lines") or [None])[0],
        "product_comparisons": (comparison or {}).get("summary"),
    }


def candidate_products(
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    comparison_products: list[dict[str, Any]],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for item in [*(comparison_products or []), primary, *(alternatives or [])]:
        if item and item.get("id") and str(item["id"]) not in seen:
            seen[str(item["id"])] = item
    products = list(seen.values())
    if len(products) >= 2:
        return products[:2]
    blob = " ".join([
        str(context.get("need") or ""),
        str(context.get("category_hint") or ""),
        " ".join(str(x) for x in (context.get("requirements") or [])),
    ]).lower()
    hdmi_task = (
        _needs_dvi(context)
        or _needs_120(context)
        or _needs_60(context)
        or "dvi" in blob
        or (("hdmi" in blob or "cable" in blob) and "soundbar" not in blob and "hdmi arc" not in blob)
    )
    if not hdmi_task:
        return products
    from . import products as product_service

    if _needs_dvi(context):
        extra = product_service.get_products([DVI_ID, BASICS_ID])
    else:
        extra = product_service.get_products([KABEL_ID, BASICS_ID])
    for item in extra:
        if item and item.get("id") and str(item["id"]) not in seen:
            seen[str(item["id"])] = item
    return list(seen.values())[:2]


def _collect_evidence(products: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in products:
        pid = str(product.get("id") or "")
        video = listed_video(product)
        rows.append({
            "source": "catalog",
            "product_id": pid,
            "evidence_type": "listed_specification",
            "claim": f"Listed video specification: {video}",
            "availability": "verified" if video != "Not listed" else "unavailable",
            "decision_relevance": "decisive" if _needs_120(context) or _needs_60(context) or _needs_dvi(context) else "supporting",
        })
        connector = connector_kind(product)
        if connector != "Not listed":
            rows.append({
                "source": "catalog",
                "product_id": pid,
                "evidence_type": "listed_specification",
                "claim": f"Listed connector: {connector}",
                "availability": "verified",
                "decision_relevance": "decisive" if _needs_dvi(context) else "supporting",
            })
        price = reference_amount(product)
        rows.append({
            "source": "catalog",
            "product_id": pid,
            "evidence_type": "catalog_price",
            "claim": f"Catalog reference price: ${price:.2f}" if price is not None else "No catalog price is available",
            "availability": "verified" if price is not None else "unavailable",
            "decision_relevance": "supporting",
        })
        intel = fetch_review_intelligence(product)
        has_text = bool(intel.get("sources"))
        rows.append({
            "source": intel.get("provider") or "catalog",
            "product_id": pid,
            "evidence_type": "customer_review",
            "claim": (intel.get("sources") or [{}])[0].get("snippet") if has_text else "No verified written review is available in the catalog",
            "availability": "verified" if has_text else "unavailable",
            "decision_relevance": "supporting" if has_text else "gap",
        })
    return rows[:10]


def _review_bundle(products: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    tokens = [token for token in ("120", "60", "dvi", "1080", "hdmi", "gaming") if token in _req_blob(context)]
    quotes: list[dict[str, Any]] = []
    lines: list[str] = []
    available = False
    for product in products:
        intel = fetch_review_intelligence(product)
        sources = [row for row in (intel.get("sources") or []) if (row.get("snippet") or "").strip()]
        if not sources:
            continue
        available = True
        relevant = [row for row in sources if not tokens or any(token in (row.get("snippet") or "").lower() for token in tokens)]
        pick = (relevant or sources)[0]
        quotes.append({"product_id": product.get("id"), "snippet": pick.get("snippet")})
        if relevant:
            lines.append(f"Catalog reviews for {short_name(product)} mention details relevant to this use case.")
        else:
            lines.append(f"{short_name(product)} has catalog reviews, but they do not directly verify this requirement.")
    if not available:
        return {
            "available": False,
            "lines": [],
            "quotes": [],
            "gap": "No verified written review is available, so I will not treat a rating as evidence of reliability or durability.",
        }
    return {"available": True, "lines": lines[:2], "quotes": quotes[:2], "gap": None}


def _req_blob(context: dict[str, Any]) -> str:
    return " ".join([
        str(context.get("need") or ""),
        str(context.get("goal") or ""),
        " ".join(str(x) for x in (context.get("requirements") or [])),
        " ".join(str(x) for x in (context.get("devices") or [])),
        str(context.get("current_priority_override") or ""),
    ]).lower()


def _taste_actually_used(
    explained: dict[str, Any],
    labels: list[str],
    memory_enabled: bool,
    context: dict[str, Any],
    winner: dict[str, Any] | None,
) -> str | None:
    if not memory_enabled or not winner:
        return None
    if _compat_first(labels) and (_needs_dvi(context) or _needs_120(context)):
        return "compatibility"
    if _wants_value(context, labels) and not _needs_120(context) and not _needs_dvi(context):
        return "value"
    return None


def _compose_take(
    *,
    message: str,
    winner: dict[str, Any] | None,
    loser: dict[str, Any] | None,
    context: dict[str, Any],
    explained: dict[str, Any],
    reviews: dict[str, Any],
    taste_used: str | None,
    labels: list[str],
) -> str:
    need_dvi = _needs_dvi(context)
    need_120 = _needs_120(context)
    need_60 = _needs_60(context)
    want_value = _wants_value(context, labels)
    wname = _spoken(winner, loser) if winner else "either product"
    lname = _spoken(loser, winner) if loser else "the other product"
    sentences: list[str] = []

    if need_dvi and winner and product_kind(winner) == "hdmi_dvi":
        sentences.append(f"{wname} is the better fit for the current older monitor.")
        sentences.append(
            f"It is listed as HDMI-to-DVI with {listed_video(winner)} video support, matching the 1080p connection you described."
        )
        if loser and product_kind(loser) == "hdmi_cable":
            sentences.append(f"A regular HDMI cable cannot connect directly to this monitor's DVI port, so {lname} is not a substitute.")
    elif need_120 and winner and listed_refresh(winner) == 120:
        sentences.append(f"If 4K 120Hz remains a hard requirement, keep {wname}.")
        if loser:
            sentences.append(
                f"It lists {_video(winner)}, while {lname} costs less and lists {_video(loser)}."
            )
        delta = _delta(winner, loser)
        extra = f" The catalog price difference is ${delta:.2f}; this is not a live checkout quote." if delta else ""
        sentences.append(f"Based on verified specifications, it is the better fit for this gaming setup.{extra}")
        if loser and float(loser.get("rating") or 0) > float(winner.get("rating") or 0):
            sentences.append("A higher rating on the cheaper cable is not a reason to drop the 120Hz requirement.")
    elif (need_60 or want_value) and winner:
        sentences.append(f"{wname} is the better fit for this use case.")
        if need_60:
            sentences.append(f"It lists {_video(winner)}, meets the 4K 60Hz need, and costs less than {lname}.")
            sentences.append("If you do not need 120Hz, there is no reason to pay for the higher refresh-rate specification.")
        else:
            sentences.append(f"Among products that meet the current need, its catalog price is lower than {lname}.")
    elif winner:
        sentences.append(explained.get("verdict") or f"Based on the listed specifications, I would choose {wname}.")
    else:
        sentences.append("It is too early to choose because the connector type or refresh-rate target is not clear enough.")

    if taste_used == "compatibility":
        sentences.append("This also applies your long-term preference to put compatibility first.")
    elif taste_used == "value":
        sentences.append("This also fits your habit of meeting the use requirements before optimizing price.")

    if reviews.get("available"):
        sentences.append("The catalog includes written reviews, but they do not prove performance with your device.")
    else:
        sentences.append(reviews.get("gap") or "No verified written review is available, so I will not use a rating as reliability evidence.")

    sentences.append(_change_condition(context, winner, loser))
    text = " ".join(item for item in sentences if item)
    words = text.split()
    if len(words) > 120:
        text = " ".join(words[:118]).rstrip(".,") + "."
    return text


def _angles(
    winner: dict[str, Any] | None,
    loser: dict[str, Any] | None,
    context: dict[str, Any],
    reviews: dict[str, Any],
    taste_used: str | None,
    labels: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if _needs_dvi(context) and winner:
        rows.append({"id": "fit", "title": "Connector fit", "body": f"{_spoken(winner, loser)} is listed as HDMI-to-DVI and matches this monitor's connector."})
    elif _needs_120(context) and winner:
        rows.append({"id": "refresh", "title": "Video specification", "body": f"{_spoken(winner, loser)} lists {_video(winner)}. This is based on catalog information, not unverified device testing."})
    elif winner:
        rows.append({"id": "listed", "title": "Listed specification", "body": f"{_spoken(winner, loser)} lists {_video(winner)}."})
    if winner and loser and reference_amount(winner) is not None and reference_amount(loser) is not None:
        delta = _delta(winner, loser)
        rows.append({"id": "price", "title": "Price tradeoff", "body": f"The catalog price difference is ${delta:.2f}. This is a reference difference, not a live checkout quote."})
    if reviews.get("available") and reviews.get("quotes"):
        quote = reviews["quotes"][0]
        rows.append({"id": "reviews", "title": "Review evidence", "body": f"Catalog review excerpt: “{(quote.get('snippet') or '')[:140]}”"})
    elif reviews.get("gap"):
        rows.append({"id": "gap", "title": "Evidence gap", "body": reviews["gap"]})
    if taste_used == "compatibility":
        rows.append({"id": "taste", "title": "Your preference", "body": "The current constraints align with your confirmed compatibility-first preference, so it affected ranking."})
    elif taste_used == "value":
        rows.append({"id": "taste", "title": "Your preference", "body": "Your value preference affects ranking only after the use requirements are met."})
    # keep 2–3 most useful
    preferred = [row for row in rows if row["id"] in {"fit", "refresh", "price", "reviews", "gap"}]
    extra = [row for row in rows if row not in preferred]
    return (preferred + extra)[:3]


def _change_condition(context: dict[str, Any], winner: dict[str, Any] | None, loser: dict[str, Any] | None) -> str:
    if _needs_dvi(context):
        return "This choice would change if the monitor actually uses HDMI rather than DVI."
    if _needs_120(context):
        return "This choice would change if you decide to stay at 60Hz."
    if _needs_60(context) or context.get("current_priority_override") == "find_cheaper":
        return "This choice would change if 120Hz becomes a hard requirement."
    if winner and loser:
        return "This choice would change if the connector or refresh-rate target changes."
    return "More detail about the device and use case could change this choice."


def _actions(winner: dict[str, Any] | None, loser: dict[str, Any] | None) -> list[dict[str, Any]]:
    actions = []
    if winner:
        actions.append({"id": "save", "label": "Save to My Picks", "kind": "message", "message": "Save this product to My Picks."})
    if winner and loser:
        actions.append({"id": "compare", "label": "Continue in My Picks", "kind": "message", "href": "/saved", "message": "Open My Picks"})
    actions.append({"id": "ask", "label": "Continue with Picki", "kind": "message", "message": "What else should I know before buying?"})
    return actions[:3]


def _comparison_data(products: list[dict[str, Any]], winner_id: str | None) -> dict[str, Any]:
    columns = []
    for item in products[:2]:
        columns.append({
            "product_id": item.get("id"),
            "title": _card_title(item),
            "price": reference_amount(item),
        })
    rows = [
        {"label": "Listed video", "values": [listed_video(item) for item in products[:2]]},
        {"label": "Connector compatibility", "values": [connector_kind(item) for item in products[:2]]},
        {"label": "Price", "values": [f"${reference_amount(item):.2f}" if reference_amount(item) is not None else "Not provided" for item in products[:2]]},
    ]
    useful = [row for row in rows if len(set(row["values"])) > 1 or row["label"] == "Price"]
    return {
        "winner_product_id": winner_id,
        "columns": columns,
        "rows": useful[:4],
        "summary": "This comparison uses key specifications listed in the catalog.",
    }


def _ref(product: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "product_id": product.get("id"),
        "role": role,
        "title": _card_title(product),
        "brand": product.get("brand"),
        "price": reference_amount(product),
        "spec_line": f"{connector_kind(product)} · {listed_video(product)}",
    }


def _card_title(product: dict[str, Any]) -> str:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return "KabelDirekt 8K HDMI Cable · 15ft"
    if pid == BASICS_ID:
        return "Amazon Basics HDMI Cable · 10ft"
    if pid == DVI_ID:
        return "Amazon Basics HDMI to DVI · 3ft"
    return (product.get("name") or "Product")[:64]


def _spoken(product: dict[str, Any] | None, other: dict[str, Any] | None = None) -> str:
    if not product:
        return "this product"
    pid = str(product.get("id") or "")
    if pid == DVI_ID:
        return "the Amazon Basics HDMI-to-DVI cable"
    if pid == KABEL_ID:
        return "KabelDirekt"
    if pid == BASICS_ID:
        if other and product_kind(other) == "hdmi_dvi":
            return "the regular Amazon Basics HDMI cable"
        return "the Amazon Basics HDMI cable"
    return short_name(product)


def _video(product: dict[str, Any]) -> str:
    return listed_video(product).replace("@", " ")


def _delta(left: dict[str, Any] | None, right: dict[str, Any] | None) -> float | None:
    a = reference_amount(left) if left else None
    b = reference_amount(right) if right else None
    if a is None or b is None:
        return None
    return abs(a - b)
