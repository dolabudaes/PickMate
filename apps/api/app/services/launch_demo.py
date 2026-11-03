from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..db import encode_json, execute, now_iso, one, query
from . import products as product_service

KABEL_ID = "B07GVWH35S"
BASICS_ID = "B0BGNG1294"
DVI_ID = "B0199HAOAU"
# Retained for normal catalog-analysis compatibility; curated demo fixtures
# below reference only the two products used by the coherent launch story.
TOZO_ID = "B08XPWDSWW"
DEMO_CART_IDS = (KABEL_ID, DVI_ID)

DEMO_CONV_MONITOR = "demo-old-monitor-future-upgrade"
DEMO_CONV_TV = "demo-best-value-4k-tv"
# Backward-compatible alias retained for older callers while the second
# curated fixture is restored to the HDMI TV story.
DEMO_CONV_SPEAKERS = DEMO_CONV_TV
# Legacy dynamic-test/demo IDs remain distinct from the two launch fixtures so
# their mutable contexts cannot overwrite one another.
DEMO_CONV_GAMING = "demo-4k-gaming"
DEMO_CONV_CABLE = "demo-4k-gaming"
HDMI_PRIMARY_ASIN = KABEL_ID
HDMI_CHEAPER_ASIN = BASICS_ID
HDMI_DVI_ASIN = DVI_ID

DEMO_SESSION_ID = os.getenv("PICKMATE_DEMO_SESSION_ID", "pickmate-launch-demo")
DEMO_DATA_VERSION = "2026-10-29-evidence-rich-shopping-stories-v4"
DEMO_MARKER_PREFIX = "demo-fixture-version:"
FIXTURE_CONVERSATIONS = (DEMO_CONV_MONITOR, DEMO_CONV_TV)
LEGACY_CONVERSATIONS = ("demo-4k-gaming", "demo-old-monitor", "demo-speakers-desk", "demo-everyday-wireless-earbuds")
FIXTURE_PREFERENCES = (
    "demo-pref-compatibility",
    "demo-pref-reliability",
    "demo-pref-avoid-unused-features",
    "demo-pref-compare-before-buying",
)
LEGACY_PERSONA_PREFERENCES = ("demo-pref-no-unnecessary-extras", "demo-pref-worth-extra", "demo-suggestion-compare-cheaper")
PERSONA_FIXTURE_PATH = Path(__file__).resolve().parents[4] / "data" / "demo" / "alex_morgan_persona.json"
PERSONA_MARKER_PREFIX = "demo-persona-version:"


def demo_mode() -> bool:
    return os.getenv("PICKMATE_DEMO_MODE", "true").strip().lower() not in {"0", "false", "no"}


def load_demo_persona() -> dict[str, Any]:
    return json.loads(PERSONA_FIXTURE_PATH.read_text(encoding="utf-8"))


def ensure_demo_persona_preferences(session_id: str) -> None:
    if not demo_mode():
        return
    persona = load_demo_persona()
    if session_id != persona.get("demoSessionId"):
        return
    version = str(persona.get("fixtureVersion") or "")
    marker_id = f"{PERSONA_MARKER_PREFIX}{session_id}"
    marker = one("SELECT event_type FROM interaction_events WHERE id=? AND session_id=?", (marker_id, session_id))
    if marker and marker.get("event_type") == f"persona_fixture_initialized:{version}":
        return

    ts = now_iso()
    _retire_legacy_persona_preferences(session_id)
    for preference in persona.get("longTermPreferences") or []:
        preference_id = str(preference["id"])
        existing = one(
            "SELECT created_at, updated_at, status FROM preference_memories WHERE id=? AND session_id=?",
            (preference_id, session_id),
        )
        if existing and (existing.get("updated_at") != existing.get("created_at") or existing.get("status") == "dismissed"):
            continue
        confirmed = preference.get("status") != "suggested"
        status = "active" if confirmed else "suggested"
        source_type = "explicit" if confirmed else "inferred"
        if existing:
            execute(
                "UPDATE preference_memories SET label=?, normalized_preference=?, facet=?, value=?, status=?, user_confirmed=?, source_type=?, source=?, enabled=1, priority=?, category=? WHERE id=? AND session_id=?",
                (str(preference["label"]), str(preference["label"]), str(preference["facet"]), str(preference["value"]), status, 1 if confirmed else 0, source_type, source_type, int(preference["priority"]), str(preference.get("category") or "general"), preference_id, session_id),
            )
        else:
            execute(
                "INSERT INTO preference_memories(id,session_id,facet,value,label,scope,confidence,evidence,source,enabled,created_at,updated_at,category,normalized_preference,source_type,status,user_confirmed,original_user_expression,evidence_message_ids,supporting_evidence_count,first_observed_at,product_category,priority) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (preference_id, session_id, str(preference["facet"]), str(preference["value"]), str(preference["label"]), "personal", 1.0 if confirmed else 0.58, "Local demo persona fixture", source_type, 1, ts, ts, str(preference.get("category") or "general"), str(preference["label"]), source_type, status, 1 if confirmed else 0, str(preference["label"]), "[]", 1, ts, None, int(preference["priority"])),
            )
    execute(
        "INSERT OR REPLACE INTO interaction_events(id,session_id,conversation_id,product_id,event_type,created_at) VALUES(?,?,?,?,?,?)",
        (marker_id, session_id, None, None, f"persona_fixture_initialized:{version}", ts),
    )


def resolve_demo_products() -> dict[str, dict[str, Any]]:
    found = {item["id"]: item for item in product_service.get_products(list(DEMO_CART_IDS))}
    missing = [pid for pid in DEMO_CART_IDS if pid not in found]
    if missing:
        raise RuntimeError(f"Launch demo products missing from catalog: {', '.join(missing)}")
    return found


def _price(product: dict[str, Any]) -> float | None:
    raw = (product.get("sourceFields") or {}).get("price")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _price_text(product: dict[str, Any]) -> str:
    value = _price(product)
    return f"${value:.2f}" if value is not None else "the current catalog price"


def _title(product: dict[str, Any], fallback: str) -> str:
    return str(product.get("name") or fallback)


def _ref(product: dict[str, Any], *, badge: str, spec: str, role: str = "alternative") -> dict[str, Any]:
    return {
        "product_id": product["id"], "role": role, "badge": badge,
        "title": _title(product, product["id"]), "brand": product.get("brand"),
        "price": _price(product), "spec_line": spec,
    }


def _comparison(left: dict[str, Any], right: dict[str, Any], rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "winner_product_id": None,
        "columns": [
            {"product_id": left["id"], "title": _title(left, left["id"]), "price": _price(left)},
            {"product_id": right["id"], "title": _title(right, right["id"]), "price": _price(right)},
        ],
        "rows": [{"label": label, "values": [a, b]} for label, a, b in rows],
    }


def _assistant(message_id: str, text: str, *, response_type: str = "RECOMMENDATION", refs: list[dict[str, Any]] | None = None, comparison: dict[str, Any] | None = None, details: list[dict[str, Any]] | None = None, actions: list[dict[str, Any]] | None = None, highlight: str | None = None, taste_saved: dict[str, Any] | None = None) -> dict[str, Any]:
    structured = {
        "response_type": response_type, "primary_message": text, "message": text,
        "product_refs": refs or [], "comparison_data": comparison,
        "detail_sections": details or [], "suggested_actions": actions or [],
        "decision_highlight": highlight, "evidence_status": "catalog",
    }
    row: dict[str, Any] = {"id": message_id, "from": "picki", "text": text, "structured": structured}
    if taste_saved:
        row["tasteSaved"] = taste_saved
    return row


def _user(message_id: str, text: str) -> dict[str, Any]:
    return {"id": message_id, "from": "you", "text": text}


def _review_details(products: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    from .review_provider import fetch_review_intelligence

    verified_by_product: list[list[str]] = []
    catalog_by_product: list[list[str]] = []
    for product in products:
        verified: list[str] = []
        catalog_excerpts: list[str] = []
        for source in fetch_review_intelligence(product).get("sources") or []:
            if source.get("verified") is True and source.get("snippet"):
                verified.append(f"{_title(product, product['id'])}: {source['snippet']}")
            elif source.get("snippet"):
                catalog_excerpts.append(f"{_title(product, product['id'])}: {source['snippet']}")
        verified_by_product.append(verified)
        catalog_by_product.append(catalog_excerpts)
    verified = _interleave_evidence(verified_by_product)
    catalog_excerpts = _interleave_evidence(catalog_by_product)
    if verified:
        return [{"id": "review-evidence", "title": "Verified review evidence", "collapsed": True, "lines": verified[:5]}], "verified_reviews"
    if catalog_excerpts:
        return [{
            "id": "review-evidence", "title": "Catalog review excerpts (purchase status not verified)", "collapsed": True,
            "lines": catalog_excerpts[:5],
        }], "insufficient_reviews"
    return [{
        "id": "review-evidence", "title": "Review evidence and limits", "collapsed": True,
        "lines": [
            "No verified written review excerpt is available for these exact listings in the current catalog.",
            "The recommendation therefore relies on catalog specifications, not a durability claim.",
        ],
    }], "insufficient_reviews"


def _interleave_evidence(groups: list[list[str]], limit: int = 5) -> list[str]:
    combined: list[str] = []
    for index in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if index < len(group):
                combined.append(group[index])
                if len(combined) == limit:
                    return combined
    return combined


def _monitor_messages(products: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    dvi, kabel = products[DVI_ID], products[KABEL_ID]
    opening = "Not really. Your current monitor needs an HDMI-to-DVI connection, while a future 4K monitor may need a higher-bandwidth HDMI connection.\n\nI wouldn't spend extra on a cable that doesn't solve today's problem. How far apart are your PC and monitor?"
    review_text = "I can't confidently judge connection stability from the reviews available for this exact listing. Its advertised specifications match your future target, but that doesn't prove it will be more reliable.\n\nI'd want stronger evidence about signal dropouts before calling it the safer choice."
    details, status = _review_details([dvi, kabel])
    review_message = _assistant(
        "picki-review-evidence",
        review_text,
        response_type="REVIEWS",
        refs=[],
        details=details,
        actions=[{"id": "remember", "label": "Remember how I shop", "kind": "message", "message": "That's how I usually shop. I don't mind paying a little more when something is genuinely better, but I hate paying for features I won't use. And compatibility always comes first."}],
    )
    review_message["structured"]["evidence_status"] = status
    return [
        _user("alex-monitor-opening", "I saved two cables, but I'm not sure which one I actually need. My PC has HDMI, my old monitor has DVI, and I might upgrade to a 4K 120Hz monitor later. Is there one cable I can buy for both?"),
        _assistant(
            "picki-monitor-opening",
            opening,
            response_type="CLARIFICATION",
            actions=[{
                "id": "distance",
                "label": "About two feet",
                "kind": "message",
                "message": "About two feet. I just don't want to waste money buying cables twice.",
            }],
        ),
        _user("alex-distance", "About two feet. I just don't want to waste money buying cables twice."),
        _assistant("picki-distance", f"Then I'd start with the {_price_text(dvi)} HDMI-to-DVI cable, as long as three feet gives you enough slack.\n\nIt solves the connection problem you have now. For your future monitor, I'd wait until you've confirmed its ports and refresh-rate requirements.", refs=[_ref(dvi, badge="Best fit now", spec="HDMI to DVI · 3 ft · 1080p", role="primary")]),
        _user("alex-current-use", "What do the connector, length, and video rating mean for my actual setup?"),
        _assistant(
            "picki-current-use",
            "For your current setup, the important facts are simple: HDMI at the PC end, DVI at the monitor end, and a 3 ft run for a distance of about 2 ft. The listing is aimed at a 1080p DVI display, so it solves today's connection without pretending to be the cable for a future 4K at 120Hz monitor.",
            refs=[_ref(dvi, badge="Matches today's setup", spec="HDMI to DVI · 3 ft · 1080p", role="primary")],
            details=[
                {"id": "current-spec-fit", "title": "Specification fit", "collapsed": False, "lines": ["PC output: HDMI", "Monitor input: DVI", "Listed cable length: 3 ft for an approximately 2 ft run", "Listed video use: 1080p"]},
                {"id": "current-best-use", "title": "Best use", "collapsed": True, "lines": ["Connecting the existing HDMI PC to the existing DVI monitor.", "Leave the future 4K at 120Hz purchase until the replacement monitor and its ports are confirmed."]},
                {"id": "current-evidence-limit", "title": "What the evidence can prove", "collapsed": True, "lines": ["The catalog supports connector, length, and listed video-fit claims.", "It does not prove long-term reliability or guarantee compatibility with an unknown future monitor."]},
            ],
        ),
        _user("alex-price-compare", f"The KabelDirekt is {_price_text(kabel)} and lists 4K at 120Hz. Wouldn't that be the better cable?"),
        _assistant("picki-current-comparison", f"Not for your current monitor. The {_price_text(kabel)} KabelDirekt has higher listed video capability, but it is HDMI-to-HDMI and cannot connect directly to the DVI input.\n\nThe {_price_text(dvi)} HDMI-to-DVI cable is the compatible choice for today.", response_type="COMPARE", refs=[
            _ref(dvi, badge="Fits your monitor", spec="HDMI to DVI · 3 ft", role="primary"),
            _ref(kabel, badge="For a future HDMI monitor", spec="HDMI to HDMI · 15 ft · 4K@120Hz"),
        ], comparison=_comparison(dvi, kabel, [("Best use", "Old DVI monitor", "Future HDMI monitor"), ("Video", "1080p", "4K@120Hz listed"), ("Connectors", "HDMI → DVI", "HDMI → HDMI"), ("Price", _price_text(dvi), _price_text(kabel))])),
        _user("alex-upgrade-question", "So should I buy both now to avoid shopping again when I upgrade?"),
        _assistant("picki-upgrade-comparison", "I would buy only the HDMI-to-DVI cable now. The KabelDirekt matches the future 4K 120Hz idea on paper, but your next monitor and its ports are not confirmed yet.\n\nBuying it now would mean paying for a feature you cannot use today.", response_type="TRADEOFF", refs=[
            _ref(dvi, badge="Buy for today", spec="3 ft · HDMI to DVI", role="primary"),
            _ref(kabel, badge="4K at 120Hz", spec="15 ft", role="primary"),
        ]),
        _user("alex-review-question", "Specs aren't everything. Are there complaints about black screens or connection drops with the KabelDirekt?"),
        review_message,
        _user("alex-taste-confirm", "That's how I usually shop. Compatibility comes first, and I'd rather pay a little more for something reliable. I just don't want to pay for features I'll never use. Can you remember that?"),
        _assistant("picki-taste-confirmed", "Absolutely. I'll put compatibility first, prioritize reliability, and only recommend spending more when there's a real benefit for you.", response_type="PREFERENCE_UPDATE"),
        _user("alex-save-dvi", "Great. Keep the HDMI-to-DVI cable as my choice for now. I'll revisit the KabelDirekt when I upgrade."),
        _assistant("picki-save-dvi", "Sounds good. The HDMI-to-DVI cable is your current pick, and the KabelDirekt remains saved as the future-upgrade candidate.", response_type="ACTION_RESULT", refs=[_ref(dvi, badge="Current pick", spec="HDMI to DVI · 3 ft · 1080p", role="primary"), _ref(kabel, badge="Future candidate", spec="HDMI to HDMI · 15 ft · 4K@120Hz")]),
    ]


def _tv_messages(products: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    dvi, kabel = products[DVI_ID], products[KABEL_ID]
    details, status = _review_details([kabel])
    review = _assistant(
        "picki-tv-reliability",
        "Verified reviews include both positive durability reports and isolated complaints about signal drops or early failure. That supports treating reliability as mixed evidence, not a guarantee. The listed 4K at 120Hz capability still needs compatible devices at both ends.",
        response_type="REVIEWS",
        details=details,
    )
    review["structured"]["evidence_status"] = status
    return [
        _user("alex-tv-opening", f"I'm ready to revisit the future upgrade. My next monitor will have HDMI and support 4K at 120Hz. Does the {_price_text(kabel)} KabelDirekt now make sense compared with the HDMI-to-DVI cable I bought for the old monitor?"),
        _assistant("picki-tv-opening", "Yes. This is a different job from the old-monitor purchase. The HDMI-to-DVI cable remains right for the current DVI display, while the KabelDirekt lists the HDMI-to-HDMI connection and 4K at 120Hz capability needed for the planned upgrade.\n\nYour compatibility-first preference changes the recommendation because the future device requirements are now confirmed.", response_type="COMPARE", refs=[
            _ref(dvi, badge="Current monitor", spec="HDMI to DVI · 1080p"),
            _ref(kabel, badge="Best fit for the upgrade", spec="HDMI to HDMI · 15 ft · 4K@120Hz", role="primary"),
        ], comparison=_comparison(dvi, kabel, [("Best use", "Old DVI monitor", "New 4K monitor"), ("Listed video", "1080p", "4K@120Hz"), ("Connectors", "HDMI → DVI", "HDMI → HDMI"), ("Price", _price_text(dvi), _price_text(kabel))])),
        _user("alex-tv-future-proof", "Does that mean the cheaper HDMI-to-DVI cable was the wrong purchase?"),
        _assistant("picki-tv-future-proof", "No. It solved the hardware problem you actually had and avoided paying early for capability you could not use. The KabelDirekt becomes relevant only now that the new HDMI monitor and 4K 120Hz target are concrete.", response_type="TRADEOFF", refs=[_ref(dvi, badge="Right for the old setup", spec="HDMI to DVI · 1080p"), _ref(kabel, badge="Right for the new setup", spec="HDMI to HDMI · 4K@120Hz", role="primary")]),
        _user("alex-tv-system-requirements", "What else has to support 4K at 120Hz besides the cable?"),
        _assistant(
            "picki-tv-system-requirements",
            "The cable is only one link in the chain. Your computer or console output and the monitor input must also support HDMI at 4K and 120Hz; a cable cannot add that capability to either device. The KabelDirekt listing matches the connection and target on paper, but the complete system still has to support the same mode.",
            response_type="EVIDENCE",
            refs=[_ref(kabel, badge="Specification match", spec="HDMI to HDMI · 15 ft · listed 4K@120Hz", role="primary")],
            details=[
                {"id": "upgrade-spec-fit", "title": "Specification fit", "collapsed": False, "lines": ["Cable: HDMI to HDMI", "Listed target: 4K at 120Hz", "Length: 15 ft", "Both source and display must support the same resolution and refresh rate."]},
                {"id": "upgrade-best-use", "title": "Best use", "collapsed": True, "lines": ["A confirmed HDMI monitor upgrade where the actual cable route benefits from a 15 ft length.", "Not a direct replacement for the HDMI-to-DVI cable used by the old monitor."]},
            ],
        ),
        _user("alex-tv-length", "The cable is 15 ft. Is that useful, or am I paying for length I do not need?"),
        _assistant(
            "picki-tv-length",
            "Fifteen feet is useful only if your real route needs it—for example, around a desk, wall, or entertainment unit. If the devices will sit close together, the extra length is not a performance benefit. Measure the routed distance rather than the straight-line gap before buying, because your preference is to avoid features you will not use.",
            response_type="TRADEOFF",
            refs=[_ref(kabel, badge="Measure before buying", spec="15 ft · HDMI to HDMI · listed 4K@120Hz", role="primary")],
            details=[
                {"id": "length-use", "title": "Best use", "collapsed": False, "lines": ["Choose 15 ft when the routed cable path genuinely needs the reach.", "A shorter cable is better value when the source and display are close together."]},
                {"id": "length-evidence", "title": "What the evidence can prove", "collapsed": True, "lines": ["The catalog confirms the listed 15 ft length and video capability.", "It cannot determine your required route length without a measurement."]},
            ],
        ),
        _user("alex-tv-reliability", "How reliable is the KabelDirekt? I care more about stable performance than the headline spec."),
        review,
        _user("alex-tv-decision", "The requirements are confirmed now. Keep the KabelDirekt as my upgrade choice."),
        _assistant("picki-tv-decision", "Done. The KabelDirekt is the upgrade choice because it fits the confirmed HDMI and 4K 120Hz requirements. The HDMI-to-DVI cable remains tied to the old monitor decision.", response_type="ACTION_RESULT", refs=[_ref(kabel, badge="Upgrade pick", spec="15 ft · listed 4K@120Hz", role="primary"), _ref(dvi, badge="Old-monitor pick", spec="3 ft · HDMI to DVI")]),
    ]


def _remove_fixture_records(session_id: str) -> None:
    owned = (*FIXTURE_CONVERSATIONS, *LEGACY_CONVERSATIONS)
    placeholders = ",".join("?" for _ in owned)
    for table in ("shopping_sessions", "conversation_context"):
        execute(f"DELETE FROM {table} WHERE conversation_id IN ({placeholders})", owned)
    execute(
        f"DELETE FROM conversation_products WHERE session_id=? AND conversation_id IN ({placeholders}) AND product_id=?",
        (session_id, *owned, BASICS_ID),
    )
    execute(f"DELETE FROM picki_conversations WHERE session_id=? AND id IN ({placeholders})", (session_id, *owned))


def reset_demo_session(session_id: str) -> None:
    _remove_fixture_records(session_id)


def _save_conversation(session_id: str, conversation_id: str, title: str, state: dict[str, Any]) -> None:
    ts = now_iso()
    existing = one("SELECT created_at FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id))
    execute("INSERT OR REPLACE INTO picki_conversations(id,session_id,title,state_json,created_at,updated_at) VALUES(?,?,?,?,?,?)", (conversation_id, session_id, title, encode_json(state), existing["created_at"] if existing else ts, ts))


def _save_context(session_id: str, conversation_id: str, context: dict[str, Any], product_ids: list[str]) -> None:
    ts = now_iso()
    execute("INSERT OR REPLACE INTO conversation_context(conversation_id,session_id,context_json,updated_at) VALUES(?,?,?,?)", (conversation_id, session_id, encode_json(context), ts))
    for product_id in product_ids:
        execute("INSERT OR IGNORE INTO conversation_products(conversation_id,session_id,product_id,created_at) VALUES(?,?,?,?)", (conversation_id, session_id, product_id, ts))


def _ensure_demo_product_relationships(session_id: str) -> None:
    expected = {
        DEMO_CONV_MONITOR: [DVI_ID, KABEL_ID],
        DEMO_CONV_TV: [DVI_ID, KABEL_ID],
    }
    ts = now_iso()
    for conversation_id, product_ids in expected.items():
        if not one("SELECT id FROM picki_conversations WHERE id=? AND session_id=?", (conversation_id, session_id)):
            continue
        for product_id in product_ids:
            execute(
                "INSERT OR IGNORE INTO conversation_products(conversation_id,session_id,product_id,created_at) VALUES(?,?,?,?)",
                (conversation_id, session_id, product_id, ts),
            )


def _save_preference(session_id: str, preference_id: str, *, label: str, facet: str, value: str, priority: int, confirmed: bool, expression: str) -> None:
    existing = one(
        "SELECT created_at,updated_at,status FROM preference_memories WHERE id=? AND session_id=?",
        (preference_id, session_id),
    )
    ts = now_iso()
    source_type = "explicit" if confirmed else "inferred"
    status = "active" if confirmed else "suggested"
    evidence = [
        {"conversation_id": DEMO_CONV_MONITOR, "snippet": expression},
        {"conversation_id": DEMO_CONV_TV, "snippet": expression},
    ]
    category = "compatibility" if facet == "compatibility" else "quality" if facet == "reliability" else "price_value"
    if existing:
        if existing.get("updated_at") != existing.get("created_at") or existing.get("status") == "dismissed":
            return
        execute(
            "UPDATE preference_memories SET facet=?,value=?,label=?,scope='personal',confidence=?,evidence=?,source=?,enabled=1,"
            "category=?,normalized_preference=?,source_type=?,status=?,user_confirmed=?,original_user_expression=?,"
            "evidence_message_ids=?,supporting_evidence_count=2,priority=? WHERE id=? AND session_id=?",
            (facet, value, label, 0.95 if confirmed else 0.58, expression, source_type, category, label, source_type, status,
             1 if confirmed else 0, expression, encode_json(evidence), priority, preference_id, session_id),
        )
        return
    execute(
        "INSERT OR REPLACE INTO preference_memories(id,session_id,facet,value,label,scope,confidence,evidence,source,enabled,created_at,updated_at,category,normalized_preference,source_type,status,user_confirmed,original_user_expression,evidence_message_ids,supporting_evidence_count,first_observed_at,product_category,priority) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (preference_id, session_id, facet, value, label, "personal", 0.95 if confirmed else 0.58, expression, source_type, 1, ts, ts, category, label, source_type, status, 1 if confirmed else 0, expression, encode_json(evidence), 2, ts, None, priority),
    )


def _retire_legacy_persona_preferences(session_id: str) -> None:
    for legacy_id in LEGACY_PERSONA_PREFERENCES:
        legacy = one(
            "SELECT created_at,updated_at,status FROM preference_memories WHERE id=? AND session_id=?",
            (legacy_id, session_id),
        )
        if legacy and legacy.get("created_at") == legacy.get("updated_at") and legacy.get("status") != "dismissed":
            execute("DELETE FROM preference_memories WHERE id=? AND session_id=?", (legacy_id, session_id))


def _retire_previous_fixture_products(session_id: str) -> None:
    fixture_ids = ",".join("?" for _ in FIXTURE_CONVERSATIONS)
    fixture_cart = query(
        f"SELECT DISTINCT c.id FROM cart_items c JOIN cart_item_provenance p ON p.cart_item_id=c.id "
        f"WHERE c.session_id=? AND c.product_id=? AND p.conversation_id IN ({fixture_ids}) "
        f"AND NOT EXISTS (SELECT 1 FROM cart_item_provenance user_p WHERE user_p.cart_item_id=c.id "
        f"AND (user_p.conversation_id IS NULL OR user_p.conversation_id NOT IN ({fixture_ids}) OR user_p.source_type!='chat'))",
        (session_id, BASICS_ID, *FIXTURE_CONVERSATIONS, *FIXTURE_CONVERSATIONS),
    )
    for row in fixture_cart:
        execute("DELETE FROM cart_item_provenance WHERE cart_item_id=?", (row["id"],))
        execute("DELETE FROM cart_items WHERE id=?", (row["id"],))
    execute(
        "DELETE FROM saved_picks WHERE session_id=? AND product_id=? AND conversation_id=? AND reason=?",
        (session_id, BASICS_ID, DEMO_CONV_MONITOR, "Lower-cost HDMI candidate discussed with Picki"),
    )


def _consolidate_fixture_preferences(session_id: str) -> None:
    for preference_id in FIXTURE_PREFERENCES:
        fixture = one(
            "SELECT normalized_preference,facet,value FROM preference_memories WHERE id=? AND session_id=?",
            (preference_id, session_id),
        )
        if not fixture:
            continue
        duplicates = query(
            "SELECT id FROM preference_memories WHERE session_id=? AND id!=? AND enabled=1 "
            "AND status NOT IN ('dismissed','superseded') AND (normalized_preference=? OR (facet=? AND value=?))",
            (session_id, preference_id, fixture.get("normalized_preference"), fixture.get("facet"), fixture.get("value")),
        )
        for duplicate in duplicates:
            execute(
                "UPDATE preference_memories SET status='superseded',enabled=0,superseded_by=?,updated_at=? WHERE id=? AND session_id=?",
                (preference_id, now_iso(), duplicate["id"], session_id),
            )


async def seed_launch_demo(session_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    from .events import ensure_session
    from .shopping_loop import add_cart_item, list_cart, list_saved, save_pick

    products = resolve_demo_products()
    session_id = session_id or DEMO_SESSION_ID
    ensure_session(session_id)
    marker_id = f"{DEMO_MARKER_PREFIX}{session_id}"
    marker = one("SELECT event_type FROM interaction_events WHERE id=? AND session_id=?", (marker_id, session_id))
    if not force and marker and marker.get("event_type") == f"demo_fixture_seeded:{DEMO_DATA_VERSION}":
        _ensure_demo_product_relationships(session_id)
        status = demo_status(session_id)
        status["conversations"] = [item["id"] for item in status.get("conversations") or []]
        status["saved_ids"] = [item.get("product_id") for item in list_saved(session_id) if item.get("product_id") in DEMO_CART_IDS]
        status["missing"] = []
        return status
    _retire_previous_fixture_products(session_id)
    _retire_legacy_persona_preferences(session_id)
    _remove_fixture_records(session_id)
    monitor_messages = _monitor_messages(products)
    tv_messages = _tv_messages(products)
    _save_conversation(session_id, DEMO_CONV_MONITOR, "Old Monitor, Future Upgrade", {"messages": monitor_messages, "need": monitor_messages[0]["text"], "productId": DVI_ID, "origin": "picki", "subtitle": "HDMI-to-DVI now · 4K 120Hz later", "manualTitle": True, "demoVersion": DEMO_DATA_VERSION})
    _save_conversation(session_id, DEMO_CONV_TV, "Best Value for My 4K TV", {"messages": tv_messages, "need": tv_messages[0]["text"], "productId": BASICS_ID, "origin": "picki", "manualTitle": True, "demoVersion": DEMO_DATA_VERSION})
    execute("UPDATE picki_conversations SET updated_at=? WHERE id=? AND session_id=?", (now_iso(), DEMO_CONV_MONITOR, session_id))
    _save_context(session_id, DEMO_CONV_MONITOR, {"devices": ["PC with HDMI output", "Monitor with DVI input"], "requirements": ["HDMI-to-DVI", "Current distance about 2 ft"], "future_plans": ["4K@120Hz"], "category_hint": "dvi", "focus_product_ids": [DVI_ID, KABEL_ID], "compared_product_ids": [DVI_ID, KABEL_ID], "shown_product_ids": [DVI_ID, KABEL_ID], "decision_product_id": DVI_ID, "turn_log": [{"role": message["from"] if message["from"] == "you" else "assistant", "text": message["text"]} for message in monitor_messages]}, [DVI_ID, KABEL_ID])
    _save_context(session_id, DEMO_CONV_TV, {"devices": ["Future monitor with HDMI input"], "requirements": ["4K@120Hz", "HDMI-to-HDMI", "Future monitor upgrade"], "category_hint": "hdmi", "focus_product_ids": [DVI_ID, KABEL_ID], "compared_product_ids": [DVI_ID, KABEL_ID], "shown_product_ids": [DVI_ID, KABEL_ID], "decision_product_id": KABEL_ID, "turn_log": [{"role": message["from"] if message["from"] == "you" else "assistant", "text": message["text"]} for message in tv_messages]}, [DVI_ID, KABEL_ID])
    _save_preference(session_id, FIXTURE_PREFERENCES[0], label="Compatibility first", facet="compatibility", value="compatibility_first", priority=90, confirmed=True, expression="Across future shopping. And compatibility always comes first for me.")
    _save_preference(session_id, FIXTURE_PREFERENCES[1], label="Reliability matters", facet="reliability", value="reliability_matters", priority=80, confirmed=True, expression="I'd rather pay a little more for something reliable.")
    _save_preference(session_id, FIXTURE_PREFERENCES[2], label="Avoid unused features", facet="features", value="avoid_unused_features", priority=70, confirmed=True, expression="I hate paying for features I won't use.")
    _save_preference(session_id, FIXTURE_PREFERENCES[3], label="Compare before buying", facet="comparison", value="compare_before_buying", priority=60, confirmed=False, expression="I compare alternatives before deciding.")
    _consolidate_fixture_preferences(session_id)
    fixture_reasons = {
        KABEL_ID: "Future option for Alex's planned 4K 120Hz monitor upgrade",
        DVI_ID: "Best fit for Alex's current HDMI-to-DVI setup",
    }
    for product_id in DEMO_CART_IDS:
        if not one("SELECT id FROM saved_picks WHERE session_id=? AND product_id=?", (session_id, product_id)):
            save_pick(session_id, DEMO_CONV_MONITOR, product_id, fixture_reasons[product_id])
        add_cart_item(session_id, product_id, DEMO_CONV_MONITOR, "chat")
    execute(
        "INSERT OR REPLACE INTO interaction_events(id,session_id,conversation_id,product_id,event_type,created_at) VALUES(?,?,?,?,?,?)",
        (marker_id, session_id, None, None, f"demo_fixture_seeded:{DEMO_DATA_VERSION}", now_iso()),
    )
    cart = list_cart(session_id)
    saved = list_saved(session_id)
    return {"demo_version": DEMO_DATA_VERSION, "session_id": session_id, "conversations": list(FIXTURE_CONVERSATIONS), "cart_ids": [item.get("product_id") for item in cart if item.get("product_id") in DEMO_CART_IDS], "saved_ids": [item.get("product_id") for item in saved if item.get("product_id") in DEMO_CART_IDS], "products": {pid: {"id": pid, "name": products[pid].get("name"), "price": _price(products[pid])} for pid in DEMO_CART_IDS}, "missing": []}


def seed_launch_demo_sync(session_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    import asyncio
    return asyncio.run(seed_launch_demo(session_id, force=force))


def demo_status(session_id: str | None = None) -> dict[str, Any]:
    from .shopping_loop import list_cart
    session_id = session_id or DEMO_SESSION_ID
    products = resolve_demo_products()
    placeholders = ",".join("?" for _ in FIXTURE_CONVERSATIONS)
    convs = query(f"SELECT id,title FROM picki_conversations WHERE session_id=? AND id IN ({placeholders}) ORDER BY updated_at DESC", (session_id, *FIXTURE_CONVERSATIONS))
    cart = list_cart(session_id)
    marker = one("SELECT event_type FROM interaction_events WHERE id=? AND session_id=?", (f"{DEMO_MARKER_PREFIX}{session_id}", session_id))
    event_type = marker.get("event_type") if marker else ""
    stored_version = event_type.split(":", 1)[1] if event_type.startswith("demo_fixture_seeded:") else None
    return {"demo_mode": demo_mode(), "demo_version": stored_version, "session_id": session_id, "conversations": [{"id": row["id"], "title": row["title"]} for row in convs], "cart_ids": [item.get("product_id") for item in cart if item.get("product_id") in DEMO_CART_IDS], "expected_cart": list(DEMO_CART_IDS), "products": {pid: {"name": products[pid].get("name"), "price": _price(products[pid])} for pid in DEMO_CART_IDS}}
