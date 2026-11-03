from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DISPLAY_MONITOR = "display_monitor"
HDMI_CABLE = "hdmi_cable"
HDMI_DVI = "hdmi_dvi"
HEADPHONES = "headphones"
SPEAKER = "speaker"
SOUNDBAR = "soundbar"
GENERIC_AUDIO = "generic_audio"
PRODUCT_FOCUS = "product_focus"
UNKNOWN = "unknown"

HEADPHONE_MARKERS = re.compile(
    r"\b(headphones?|earbuds?|earbud|headset|in[- ]ear|over[- ]ear|ear pads?)\b",
    re.I,
)
DISPLAY_MARKERS = re.compile(
    r"\b(gaming monitor|computer monitor|\bmonitor\b.*\b(display|inch|hz|refresh|panel)\b|"
    r"\b(display|television|tv)\b.*\b(inch|4k|hdmi)\b|ultrawide monitor|curved monitor)",
    re.I,
)
MONITOR_QUERY = re.compile(r"\b(monitor|display)\b", re.I)
HDMI_QUERY = re.compile(r"\bhdmi\b", re.I)
SPEAKER_QUERY = re.compile(r"\b(speakers?|soundbars?|subwoofers?)\b", re.I)
SOUNDBAR_ACCESSORY = re.compile(r"\b(mount|bracket|remote control|wall mount|oem remote)\b", re.I)
SPEAKER_ACCESSORY = re.compile(r"\b(wall plate|banana plug|binding post|terminal|speaker (?:mount|stand|bracket|wire|cable|cover|grille))\b", re.I)
HDMI_ARC_RE = re.compile(r"hdmi[\s\-]*arc", re.I)
HDMI_DVI_RE = re.compile(r"hdmi[\s\-]*(to[\s\-]*)?dvi|dvi[\s\-]*(adapter|cable)", re.I)
CONNECT_MONITOR_RE = re.compile(r"\b(older monitor|old monitor|connect.{0,24}monitor|laptop.{0,24}monitor|monitor uses dvi)\b", re.I)


@dataclass(frozen=True)
class ShoppingIntent:
    kind: str
    query: str | None = None
    reject_reason: str | None = None


def detect_shopping_intent(
    message: str,
    *,
    product_id: str | None,
    session_context: dict[str, Any] | None,
) -> ShoppingIntent:
    text = (message or "").strip()
    lower = text.lower()
    ctx = session_context or {}
    hint = (ctx.get("category_hint") or "").lower()

    if hint == "soundbar" and not MONITOR_QUERY.search(lower) and "monitor" not in lower:
        return ShoppingIntent(SOUNDBAR, query="soundbar")
    if hint == "speaker" and not MONITOR_QUERY.search(lower) and not re.search(r"\bsoundbar\b", lower):
        return ShoppingIntent(SPEAKER, query=text or "speaker")
    if hint in {"dvi", "hdmi_dvi"} and not re.search(r"gaming monitor", lower):
        return ShoppingIntent(HDMI_DVI, query="hdmi to dvi")

    if HDMI_DVI_RE.search(lower) or (re.search(r"\bdvi\b", lower) and HDMI_QUERY.search(lower)):
        return ShoppingIntent(HDMI_DVI, query="hdmi to dvi")
    if CONNECT_MONITOR_RE.search(lower) and not re.search(r"gaming monitor|4k monitor", lower):
        return ShoppingIntent(HDMI_DVI, query="hdmi to dvi")

    if product_id and not (MONITOR_QUERY.search(lower) and not CONNECT_MONITOR_RE.search(lower)):
        if hint == "soundbar":
            return ShoppingIntent(SOUNDBAR, query="soundbar")
        if hint in {"dvi", "hdmi_dvi"}:
            return ShoppingIntent(HDMI_DVI, query="hdmi to dvi")
        if HDMI_QUERY.search(lower) or hint == "hdmi":
            return ShoppingIntent(PRODUCT_FOCUS, query="hdmi cable")
        return ShoppingIntent(PRODUCT_FOCUS)

    if (MONITOR_QUERY.search(lower) or hint == "monitor") and not CONNECT_MONITOR_RE.search(lower) and "soundbar" not in lower:
        return ShoppingIntent(
            DISPLAY_MONITOR,
            query="computer monitor display",
            reject_reason="studio_monitor_headphones",
        )

    if re.search(r"\bsoundbar\b", lower):
        return ShoppingIntent(SOUNDBAR, query="soundbar")

    if HDMI_QUERY.search(lower) or hint == "hdmi":
        return ShoppingIntent(HDMI_CABLE, query="hdmi cable")

    if re.search(r"\bheadphones?|earbuds?|headset\b", lower):
        return ShoppingIntent(HEADPHONES, query=text or "headphones")

    if SPEAKER_QUERY.search(lower):
        return ShoppingIntent(SPEAKER, query=text or "speaker")

    if len(lower.split()) >= 3:
        return ShoppingIntent(GENERIC_AUDIO, query=text)

    return ShoppingIntent(UNKNOWN, query=text if text else None)


def product_matches_intent(product: dict[str, Any], intent: ShoppingIntent) -> bool:
    if intent.kind == PRODUCT_FOCUS:
        return True
    if intent.kind == UNKNOWN:
        return True

    name = (product.get("name") or "").lower()
    blob = _product_text(product)

    if intent.kind == DISPLAY_MONITOR:
        if HEADPHONE_MARKERS.search(name) or HEADPHONE_MARKERS.search(blob):
            return False
        if re.search(
            r"\b(gaming monitor|computer monitor|lcd monitor|led monitor|oled monitor|"
            r"\d{2}\s*[-\"]?\s*inch monitor|ultrawide monitor|curved monitor|display monitor)\b",
            name,
            re.I,
        ):
            return True
        if re.search(r"\bmonitor\b", name, re.I) and re.search(r"\bseries\b", name, re.I):
            return False
        return False

    if intent.kind == HDMI_CABLE:
        if HDMI_DVI_RE.search(name) or "dvi" in name:
            return False
        return "hdmi" in name or "hdmi" in blob

    if intent.kind == HDMI_DVI:
        return bool(HDMI_DVI_RE.search(name) or HDMI_DVI_RE.search(blob) or ("dvi" in name and "hdmi" in name))

    if intent.kind == HEADPHONES:
        return bool(HEADPHONE_MARKERS.search(name) or HEADPHONE_MARKERS.search(blob))

    if intent.kind == SOUNDBAR:
        if SOUNDBAR_ACCESSORY.search(name) and not re.search(r"\b\d\.\d\b|channel", name):
            return False
        return "soundbar" in name or "soundbar" in blob

    if intent.kind == SPEAKER:
        if HEADPHONE_MARKERS.search(name):
            return False
        if SPEAKER_ACCESSORY.search(name):
            return False
        return "speaker" in name or "speaker" in blob

    return True


def filter_products_for_intent(products: list[dict[str, Any]], intent: ShoppingIntent) -> list[dict[str, Any]]:
    if intent.kind in {PRODUCT_FOCUS, UNKNOWN, GENERIC_AUDIO}:
        return products
    return [item for item in products if product_matches_intent(item, intent)]


def search_query_for_intent(intent: ShoppingIntent, message: str) -> str:
    if intent.query:
        return intent.query
    return message or "home audio"


def no_match_message(intent: ShoppingIntent) -> str:
    if intent.kind == DISPLAY_MONITOR:
        return (
            "I don't have gaming monitors in this catalog, so I can't recommend one reliably. "
            "I can help with audio for a gaming setup, though."
        )
    return "Nothing in the current catalog meets all of those requirements."


def product_text(product: dict[str, Any]) -> str:
    return _product_text(product)


def hdmi_arc_listed(product: dict[str, Any]) -> bool:
    return bool(HDMI_ARC_RE.search(_product_text(product)))


def apply_hard_filters(
    products: list[dict[str, Any]],
    *,
    budget_max: float | None,
    requirements: list[str] | None,
) -> list[dict[str, Any]]:
    reqs = [str(item).lower() for item in (requirements or [])]
    needs_arc = any("hdmi" in item and "arc" in item for item in reqs)
    needs_120 = any("120" in item for item in reqs)
    needs_dvi = any("dvi" in item for item in reqs)
    needs_wired_audio = any("wired" in item and ("audio" in item or "input" in item or "connection" in item) for item in reqs)
    kept: list[dict[str, Any]] = []
    for product in products:
        price = _safe_price(product)
        if budget_max is not None and price is not None and price > float(budget_max):
            continue
        blob = _product_text(product)
        if needs_dvi and not HDMI_DVI_RE.search(blob):
            continue
        if needs_arc and not HDMI_ARC_RE.search(blob):
            continue
        if needs_120 and not re.search(r"120|48\s*gbps|hdmi\s*2\.1", blob, re.I):
            continue
        if needs_wired_audio and not re.search(r"\baux\b|auxiliary|3\.5\s*mm|\brca\b|line[ -]?in|wired (?:audio|input|connection)", blob, re.I):
            continue
        kept.append(product)
    return kept


def _safe_price(product: dict[str, Any]) -> float | None:
    raw = (product.get("sourceFields") or {}).get("price")
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _product_text(product: dict[str, Any]) -> str:
    source = product.get("sourceFields") or {}
    parts = [
        product.get("name") or "",
        product.get("category") or "",
        " ".join(source.get("features") or []),
        " ".join(f"{k} {v}" for k, v in (source.get("details") or {}).items()),
    ]
    return " ".join(parts).lower()
