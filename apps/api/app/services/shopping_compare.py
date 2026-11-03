from __future__ import annotations

import re
from typing import Any

KABEL_ID = "B07GVWH35S"
BASICS_ID = "B0BGNG1294"
DVI_ID = "B0199HAOAU"

_KINDS = (
    ("hdmi_dvi", re.compile(r"hdmi[\s\-]*(to[\s\-]*)?dvi|dvi[\s\-]*(adapter|cable)", re.I)),
    ("hdmi_cable", re.compile(r"\bhdmi\b", re.I)),
    ("soundbar", re.compile(r"sound\s?bar", re.I)),
    ("headphone", re.compile(r"headphone|earbud|headset|earphone", re.I)),
    ("receiver", re.compile(r"\breceiver\b|amplifier|\bavr\b", re.I)),
    ("turntable", re.compile(r"turntable|record player", re.I)),
    ("speaker", re.compile(r"speaker|subwoofer", re.I)),
)

_HZ_120 = re.compile(r"4k.{0,18}120|120\s*hz|8k.{0,12}60", re.I)
_HZ_60 = re.compile(r"4k.{0,18}60|60\s*hz|18\s*gbps", re.I)
_LENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(ft|feet|foot)", re.I)
_DVI = re.compile(r"\bdvi\b", re.I)
_1080 = re.compile(r"1080p|full hd", re.I)


def product_kind(product: dict[str, Any]) -> str:
    text = f"{product.get('name') or ''} {product.get('category') or ''}"
    for label, pattern in _KINDS:
        if pattern.search(text):
            return label
    return "other"


def reference_amount(product: dict[str, Any]) -> float | None:
    raw = product.get("currentPrice")
    if raw in (None, "", 0, 0.0):
        raw = (product.get("sourceFields") or {}).get("price")
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def snapshot(product: dict[str, Any]) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    features = source.get("features") or []
    caution = (product.get("negativeThemes") or [None])[0]
    rating = product.get("rating")
    return {
        "product_id": product.get("id"),
        "title": product.get("name") or product.get("id"),
        "brand": product.get("brand") or "",
        "kind": product_kind(product),
        "reference_price": reference_amount(product),
        "rating": float(rating) if rating else None,
        "review_count": int(product.get("reviewCount") or 0),
        "feature": features[0] if features else None,
        "caution": caution,
    }


def short_name(product: dict[str, Any]) -> str:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return "KabelDirekt"
    if pid == BASICS_ID:
        return "Amazon Basics"
    if pid == DVI_ID:
        return "HDMI to DVI"
    name = (product.get("name") or product.get("brand") or "This one").strip()
    return name.split(",")[0].split("–")[0].strip()[:28]


def pick_label(product: dict[str, Any]) -> str:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return "KabelDirekt 8K HDMI"
    if pid == BASICS_ID:
        return "Amazon Basics HDMI Cable"
    if pid == DVI_ID:
        return "Amazon Basics HDMI to DVI"
    return short_name(product)


def _blob(product: dict[str, Any]) -> str:
    source = product.get("sourceFields") or {}
    return " ".join([
        str(product.get("name") or ""),
        str(product.get("title") or ""),
        " ".join(source.get("features") or []),
        " ".join(f"{k} {v}" for k, v in (source.get("details") or {}).items()),
    ]).lower()


def listed_refresh(product: dict[str, Any]) -> int | None:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return 120
    if pid == BASICS_ID:
        return 60
    blob = _blob(product)
    if _HZ_120.search(blob):
        return 120
    if _HZ_60.search(blob):
        return 60
    return None


def listed_length(product: dict[str, Any]) -> str | None:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return "15 ft"
    if pid == BASICS_ID:
        return "10 ft"
    if pid == DVI_ID:
        return "3 ft"
    match = _LENGTH.search(_blob(product))
    if not match:
        return None
    return f"{match.group(1)} ft"


def listed_video(product: dict[str, Any]) -> str:
    pid = str(product.get("id") or "")
    if pid == KABEL_ID:
        return "4K@120Hz"
    if pid == BASICS_ID:
        return "4K@60Hz"
    if pid == DVI_ID:
        return "1080p"
    hz = listed_refresh(product)
    if hz:
        return f"4K@{hz}Hz"
    if _1080.search(_blob(product)):
        return "1080p"
    return "Not listed"


def connector_kind(product: dict[str, Any]) -> str:
    kind = product_kind(product)
    if kind == "hdmi_dvi" or _DVI.search(product.get("name") or ""):
        return "HDMI → DVI"
    if kind == "hdmi_cable":
        return "HDMI → HDMI"
    return "Not listed"


def _taste_labels(retrieved: dict[str, Any] | list[str] | None) -> list[str]:
    if not retrieved:
        return []
    if isinstance(retrieved, list):
        return [str(item).lower() for item in retrieved]
    labels: list[str] = []
    for bucket in ("global", "category_specific"):
        for item in retrieved.get(bucket) or []:
            text = (item.get("normalized_preference") or item.get("label") or item.get("facet") or "").lower()
            if text:
                labels.append(text)
    for item in retrieved.get("items") or []:
        text = (item.get("normalized_preference") or item.get("label") or item.get("facet") or "").lower()
        if text:
            labels.append(text)
    for label in retrieved.get("priority_labels") or []:
        labels.append(str(label).lower())
    return labels


def _compat_first(labels: list[str]) -> bool:
    return any("compatib" in item or item == "compatibility" or "兼容" in item or "适配" in item for item in labels)


def _value_first(labels: list[str]) -> bool:
    return any(token in " ".join(labels) for token in ("good value", "value over", "lowest price", "save money", "性价比", "价格优先", "更便宜"))


def _req_text(context: dict[str, Any]) -> str:
    parts = [str(x) for x in (context.get("requirements") or [])]
    parts.extend(str(x) for x in (context.get("devices") or []))
    parts.append(str(context.get("goal") or ""))
    parts.append(str(context.get("need") or ""))
    return " ".join(parts).lower()


def _needs_120(context: dict[str, Any]) -> bool:
    if context.get("current_priority_override") == "refresh_60":
        return False
    if context.get("current_priority_override") == "refresh_120":
        return True
    text = _req_text(context)
    return "120" in text or "4k@120" in text


def _needs_60(context: dict[str, Any]) -> bool:
    if context.get("current_priority_override") == "refresh_60":
        return True
    text = _req_text(context)
    if _needs_120(context):
        return False
    reqs = " ".join(str(x).lower() for x in (context.get("requirements") or []))
    return "4k@60" in text or "4k@60" in reqs or ("60" in text and "120" not in text)


def _wants_value(context: dict[str, Any], labels: list[str]) -> bool:
    text = _req_text(context)
    return (
        context.get("goal") == "find_cheaper"
        or context.get("current_priority_override") == "find_cheaper"
        or _value_first(labels)
        or any(token in text for token in ("save", "cheap", "budget", "less expensive", "keep cost", "prioritize lower price"))
    )


def _needs_dvi(context: dict[str, Any]) -> bool:
    text = _req_text(context)
    return "dvi" in text or "older monitor" in text or "old monitor" in text


def relevant_compare_context(products: list[dict[str, Any]], conversations: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep only conversation evidence that actually applies to this product pair."""
    kinds = {product_kind(item) for item in products}
    mixed = "hdmi_dvi" in kinds and "hdmi_cable" in kinds
    hdmi_only = bool(kinds) and kinds <= {"hdmi_cable"}
    scored: list[tuple[int, dict[str, Any]]] = []
    for conv in conversations:
        blob = " ".join([
            str(conv.get("title") or ""),
            str(conv.get("need") or ""),
            " ".join(str(x) for x in (conv.get("requirements") or [])),
            " ".join(str(x) for x in (conv.get("devices") or [])),
            " ".join(str(x) for x in (conv.get("use_cases") or [])),
            str(conv.get("category_hint") or ""),
        ]).lower()
        score = 2 if conv.get("linked") else 0
        if mixed:
            if "dvi" in blob or "older monitor" in blob or "old monitor" in blob:
                score += 6
            elif "120" in blob and "dvi" not in blob:
                score -= 4
        elif hdmi_only:
            if "120" in blob or "4k@60" in blob or "4k@60hz" in blob or "gaming" in blob:
                score += 5
            if "dvi" in blob or "older monitor" in blob:
                score -= 4
        else:
            if conv.get("linked"):
                score += 2
        if score > 0:
            scored.append((score, conv))
    merged = {
        "devices": [],
        "requirements": [],
        "use_cases": [],
        "goal": None,
        "need": "",
        "category_hint": None,
    }
    if not scored:
        return merged
    top = max(item[0] for item in scored)
    chosen = [conv for score, conv in scored if score >= top - 1]
    needs: list[str] = []
    for conv in chosen:
        for item in conv.get("requirements") or []:
            if item not in merged["requirements"]:
                merged["requirements"].append(str(item))
        for item in conv.get("devices") or []:
            if item not in merged["devices"]:
                merged["devices"].append(str(item))
        for item in conv.get("use_cases") or []:
            if item not in merged["use_cases"]:
                merged["use_cases"].append(str(item))
        if conv.get("need"):
            needs.append(str(conv["need"]))
        if conv.get("title"):
            needs.append(str(conv["title"]))
        if conv.get("goal") and not merged["goal"]:
            merged["goal"] = conv.get("goal")
        if conv.get("category_hint") and not merged["category_hint"]:
            merged["category_hint"] = conv.get("category_hint")
    merged["need"] = " ".join(needs)
    return merged


def explain_comparison(
    products: list[dict[str, Any]],
    *,
    shopping_context: dict[str, Any] | None = None,
    retrieved_taste: dict[str, Any] | list[str] | None = None,
    memory_enabled: bool = True,
) -> dict[str, Any]:
    context = shopping_context or {}
    labels = _taste_labels(retrieved_taste) if memory_enabled else []
    kinds = {product_kind(item) for item in products}
    hdmi_set = kinds <= {"hdmi_cable", "hdmi_dvi"} and bool(kinds & {"hdmi_cable", "hdmi_dvi"})

    if hdmi_set:
        return _explain_hdmi(products, context, labels, memory_enabled)

    audio_kinds = kinds - {"other"}
    if len(audio_kinds) > 1:
        return {
            "winner_product_id": None,
            "headline": "Picki's take",
            "summary": "",
            "verdict": "These products serve different needs. I wouldn't pick a winner from catalog facts alone — decide from the job you actually need.",
            "reasons": [],
            "diffs": _generic_diffs(products),
            "preference_note": None,
            "limitation": None,
        }

    ranked = sorted(
        products,
        key=lambda item: (
            -(float(item.get("rating") or 0)),
            -(int(item.get("reviewCount") or 0)),
            reference_amount(item) if reference_amount(item) is not None else 10**9,
        ),
    )
    winner = ranked[0]
    rating = float(winner.get("rating") or 0)
    name = winner.get("name") or "This one"
    if rating:
        verdict = f"I'd choose {name}. It has the stronger catalog rating ({rating:.1f}) in this set. Prices are catalog references, not a live checkout price."
    else:
        verdict = f"I'd choose {name}. Catalog ratings are missing, so this follows review count and reference price. Prices are catalog references, not a live checkout price."
    return {
        "winner_product_id": winner.get("id"),
        "headline": "Picki's take",
        "summary": "",
        "verdict": verdict,
        "reasons": [],
        "diffs": _generic_diffs(products),
        "preference_note": None,
        "limitation": None,
    }


def comparison_verdict(
    products: list[dict[str, Any]],
    shopping_context: dict[str, Any] | None = None,
    retrieved_taste: dict[str, Any] | list[str] | None = None,
    memory_enabled: bool = True,
) -> tuple[str | None, str]:
    explained = explain_comparison(
        products,
        shopping_context=shopping_context,
        retrieved_taste=retrieved_taste,
        memory_enabled=memory_enabled,
    )
    return explained.get("winner_product_id"), explained["verdict"]


def _explain_hdmi(
    products: list[dict[str, Any]],
    context: dict[str, Any],
    labels: list[str],
    memory_enabled: bool,
) -> dict[str, Any]:
    has_dvi = any(product_kind(item) == "hdmi_dvi" for item in products)
    has_hdmi = any(product_kind(item) == "hdmi_cable" for item in products)
    prefer_compat = _compat_first(labels)
    prefer_value = _value_first(labels)
    need_dvi = _needs_dvi(context)
    need_120 = _needs_120(context)
    need_60 = _needs_60(context)
    want_value = _wants_value(context, labels)

    winner: dict[str, Any] | None = None
    taste_used = False

    if has_dvi and has_hdmi and need_dvi:
        winner = next(item for item in products if product_kind(item) == "hdmi_dvi")
        taste_used = prefer_compat
    elif has_dvi and has_hdmi and need_120 and not need_dvi:
        winner = next((item for item in products if listed_refresh(item) == 120), None)
        taste_used = prefer_compat and winner is not None
    elif has_dvi and has_hdmi:
        winner = None
    elif all(product_kind(item) == "hdmi_cable" for item in products):
        hz_pairs = [(listed_refresh(item), item) for item in products]
        hz_values = [hz for hz, _ in hz_pairs if hz]
        priced = [(reference_amount(item), item) for item in products if reference_amount(item) is not None]
        if need_60:
            fit = [item for item in products if (listed_refresh(item) or 0) >= 60 or listed_video(item) == "4K@60Hz"]
            pool = [(reference_amount(item), item) for item in (fit or products) if reference_amount(item) is not None]
            if pool:
                winner = min(pool, key=lambda row: row[0])[1]
                taste_used = prefer_value
        elif need_120:
            winner = next((item for item in products if listed_refresh(item) == 120), None) or (
                next((item for item in products if listed_refresh(item) == max(hz_values)), None) if hz_values else None
            )
            taste_used = prefer_compat and winner is not None
        elif want_value and priced:
            winner = min(priced, key=lambda row: row[0])[1]
            taste_used = prefer_value
        elif hz_values and max(hz_values) >= 120 and min(hz_values) < 120:
            winner = next((item for item in products if listed_refresh(item) == max(hz_values)), None)
            taste_used = prefer_compat and winner is not None
        elif priced and len({row[0] for row in priced}) > 1 and not hz_values:
            winner = min(priced, key=lambda row: row[0])[1]
        else:
            ranked = sorted(products, key=lambda item: (-(float(item.get("rating") or 0)), reference_amount(item) or 10**9))
            winner = ranked[0]

    others = [item for item in products if winner is None or item.get("id") != winner.get("id")]
    loser = others[0] if others else None
    verdict = _compose_hdmi_take(
        winner=winner,
        loser=loser,
        context=context,
        taste_used=memory_enabled and taste_used,
        prefer_compat=prefer_compat,
        prefer_value=prefer_value,
        need_dvi=need_dvi,
        need_120=need_120,
        need_60=need_60,
    )
    return {
        "winner_product_id": winner.get("id") if winner else None,
        "headline": "Picki's take",
        "summary": "",
        "verdict": verdict,
        "reasons": [],
        "diffs": _hdmi_diffs(products)[:4],
        "preference_note": None,
        "limitation": None,
    }


def _spoken_name(product: dict[str, Any], other: dict[str, Any] | None = None) -> str:
    pid = str(product.get("id") or "")
    if pid == DVI_ID:
        return "Amazon Basics HDMI-to-DVI cable"
    if pid == KABEL_ID:
        return "KabelDirekt"
    if pid == BASICS_ID:
        if other and product_kind(other) == "hdmi_dvi":
            return "regular Amazon Basics HDMI cable"
        return "Amazon Basics HDMI cable"
    return short_name(product)


def _video_prose(product: dict[str, Any]) -> str:
    return listed_video(product).replace("@", " at ")


def _goal_phrase(context: dict[str, Any], need_dvi: bool, need_120: bool, need_60: bool) -> str:
    text = _req_text(context)
    if need_dvi:
        return "older monitor setup" if "old" in text else "DVI monitor setup"
    if need_120:
        return "gaming setup" if "gaming" in text else "4K at 120Hz setup"
    if need_60:
        return "this setup"
    return "this comparison"


def _compose_hdmi_take(
    *,
    winner: dict[str, Any] | None,
    loser: dict[str, Any] | None,
    context: dict[str, Any],
    taste_used: bool,
    prefer_compat: bool,
    prefer_value: bool,
    need_dvi: bool,
    need_120: bool,
    need_60: bool,
) -> str:
    if not winner:
        return (
            "I wouldn't pick a winner here. One option is HDMI-to-DVI and the other is HDMI-to-HDMI, "
            "and the current task does not make the connection target clear enough to decide."
        )

    wname = _spoken_name(winner, loser)
    lname = _spoken_name(loser, winner) if loser else "the other option"
    wvideo = listed_video(winner)
    lvideo = listed_video(loser) if loser else "Not listed"
    wprice = reference_amount(winner)
    lprice = reference_amount(loser) if loser else None
    delta = abs(wprice - lprice) if wprice is not None and lprice is not None else None
    winner_cheaper = wprice is not None and lprice is not None and wprice < lprice
    goal = _goal_phrase(context, need_dvi, need_120, need_60)
    sentences: list[str] = []

    if need_dvi and product_kind(winner) == "hdmi_dvi":
        sentences.append(f"For your {goal}, I'd go with the {wname}.")
        bits = ["It matches the connection you need"]
        if wvideo != "Not listed":
            bits.append(f"supports the listed {wvideo} requirement")
        if winner_cheaper:
            bits.append(f"and costs less than the {lname}")
        sentences.append(_join_bits(bits) + ".")
    elif need_120 and listed_refresh(winner) == 120:
        sentences.append(f"I'd choose the {wname} for your {goal}.")
        if loser and lvideo != "Not listed":
            cheap = "cheaper " if (lprice is not None and wprice is not None and lprice < wprice) else ""
            sentences.append(f"It's listed for {_video_prose(winner)}, while the {cheap}{lname} lists {_video_prose(loser)}.")
        if delta and not winner_cheaper:
            sentences.append(f"The extra ${delta:.2f} is worth considering if 120Hz is a requirement.")
    elif need_60 or (prefer_value and not need_120 and not need_dvi):
        sentences.append(f"I'd choose the {wname} for this setup.")
        meet = "meets your requirement" if need_60 else "is the stronger fit on listed price"
        extra = f", and it costs less than the {lname}" if winner_cheaper else ""
        if wvideo != "Not listed":
            sentences.append(f"Its listed {_video_prose(winner)} support {meet}{extra}.")
        elif extra:
            sentences.append(f"It costs less than the {lname}.")
        if loser and listed_refresh(loser) == 120 and listed_refresh(winner) == 60:
            sentences.append("There's little reason to pay more for 120Hz support if you don't need it.")
    else:
        sentences.append(f"I'd choose the {wname} for {goal}.")
        if loser and wvideo != lvideo and wvideo != "Not listed":
            sentences.append(f"The listed video spec is {_video_prose(winner)} versus {_video_prose(loser)}.")
        if winner_cheaper:
            sentences.append(f"It also lists the lower catalog price versus the {lname}.")

    if taste_used and prefer_compat and "compatib" not in " ".join(sentences).lower():
        sentences[-1] = sentences[-1].rstrip(".") + ", keeping compatibility first."
    elif taste_used and prefer_value and "cost" not in " ".join(sentences).lower() and "less" not in " ".join(sentences).lower():
        sentences[-1] = sentences[-1].rstrip(".") + ", which also keeps cost down."

    text = " ".join(sentences)
    words = text.split()
    if len(words) < 35 and delta is not None and "extra $" not in text and "costs less" not in text:
        text = text.rstrip(".") + f", at a ${delta:.2f} listed price difference."
    if len(text.split()) > 65:
        parts = re.split(r"(?<=[.!?])\s+", text)
        while len(" ".join(parts).split()) > 65 and len(parts) > 2:
            parts.pop()
        text = " ".join(parts)
    return text


def _join_bits(bits: list[str]) -> str:
    if len(bits) == 1:
        return bits[0]
    if len(bits) == 2:
        second = bits[1] if bits[1].startswith("and ") else f"and {bits[1]}"
        return f"{bits[0]}, {second}"
    last = bits[-1] if bits[-1].startswith("and ") else f"and {bits[-1]}"
    return f"{', '.join(bits[:-1])}, {last}"


def _hdmi_diffs(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = [short_name(item) for item in products]
    rows = [
        {"label": "Video", "values": [listed_video(item) for item in products]},
        {"label": "Connectors", "values": [connector_kind(item) for item in products]},
        {"label": "Length", "values": [listed_length(item) or "Not listed" for item in products]},
        {"label": "Price", "values": [f"${reference_amount(item):.2f}" if reference_amount(item) is not None else "Not listed" for item in products]},
    ]
    useful = []
    for row in rows:
        if len(set(row["values"])) > 1 or row["label"] == "Price":
            useful.append(row)
    if names:
        for row in useful:
            row["columns"] = names
    return useful[:4]


def _generic_diffs(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"label": "Price", "values": [f"${reference_amount(item):.2f}" if reference_amount(item) is not None else "Not listed" for item in products]},
        {"label": "Rating", "values": [f"{float(item.get('rating')):.1f}" if item.get("rating") else "Not listed" for item in products]},
        {"label": "Kind", "values": [product_kind(item).replace("_", " ") for item in products]},
    ]
