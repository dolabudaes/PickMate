from __future__ import annotations

import secrets
from typing import Any

from ..db import decode_json, encode_json, execute, now_iso, one, query
from ..harness.agent_harness import PickiAgentHarness
from ..harness.harness import PickMateHarness
from ..schemas import HarnessRequest
from ..services.events import ensure_session
from ..services.products import get_product
from .shopping_intent import (
    apply_update,
    blank_session,
    card,
    cheaper_ceiling,
    compose_reply,
    evidenced_tradeoff,
    interpret,
    looks_cleaner,
    memory_candidate,
    price_delta,
    retrieval_plan,
    why_for_you,
)

harness = PickMateHarness()
agent_harness = PickiAgentHarness()


async def run_turn(session_id: str, conversation_id: str, message: str, action: str, product_id: str | None) -> dict[str, Any]:
    ensure_session(session_id)
    if action == "message" and message.strip():
        return await agent_harness.run_chat_turn(session_id, conversation_id, message.strip(), product_id)
    state = load_session(conversation_id, session_id)
    previous = get_product(state.get("current_product_id")) if state.get("current_product_id") else None
    update = interpret(message, action, state)
    state = apply_update(state, update, product_id)
    if update["rerank"] == "cheaper" and previous:
        ceiling = cheaper_ceiling(_safe_price(previous), state.get("budget_max"))
        if ceiling is not None:
            state["budget_max"] = ceiling
            state["budget_ephemeral"] = True
    memories = list_memories(session_id) if memory_enabled(session_id) else []
    memory_event = maybe_store_memory(session_id, message, update)
    plan = retrieval_plan(state, update, memories if state.get("recipient") != "gift" else [])

    if update["explain"] == "why" and previous:
        payload = _payload(conversation_id, compose_reply(kind="why", why=why_for_you(previous, state.get("budget_max"), state.get("style")), caution=_caution(previous)), previous, _alts(state), state, [], memory_event)
        _persist(conversation_id, session_id, state, "why_this", previous.get("id"))
        return payload
    if update["explain"] == "compare":
        return _compare(conversation_id, session_id, state, previous, memory_event)

    if update["rerank"] == "promote" and product_id:
        chosen = get_product(product_id)
        if chosen:
            return _finish(conversation_id, session_id, state, previous, chosen, [], "style", memory_event, plan)

    response = await harness.run(HarnessRequest(
        session_id=session_id,
        action="recommend",
        message=plan["message"],
        current_product_id=product_id if update["rerank"] == "focus" else None,
        exclude_product_ids=plan["exclude_product_ids"],
        prefer_terms=plan["prefer_terms"],
        max_price=plan["max_price"],
    ))
    ranked = [item["product"] for item in [response.primary, *response.alternatives] if item and item.get("product")]
    if update["rerank"] == "focus" and product_id:
        focused = get_product(product_id)
        alternatives = [item for item in ranked if item.get("id") != product_id][:2]
        if focused:
            return _finish(conversation_id, session_id, state, previous, focused, alternatives, "focus", memory_event, plan)
    chosen = ranked[0] if ranked else None
    alternatives = ranked[1:3]
    if chosen is None and previous and update["rerank"] in {"cheaper", "style"}:
        text = compose_reply(kind="kept" if update["rerank"] == "cheaper" else "style_kept")
        payload = _payload(conversation_id, text, previous, _alts(state), state, [], memory_event)
        _persist(conversation_id, session_id, state, update["rerank"], previous.get("id"))
        return payload
    if previous and chosen and chosen.get("id") == previous.get("id") and update["rerank"] in {"cheaper", "style"}:
        text = compose_reply(kind="kept" if update["rerank"] == "cheaper" else "style_kept")
        payload = _payload(conversation_id, text, previous, alternatives, state, [], memory_event)
        _persist(conversation_id, session_id, state, update["rerank"], previous.get("id"))
        return payload
    if previous and chosen and update["rerank"] == "cheaper" and price_delta(previous, chosen) is None:
        text = compose_reply(kind="kept")
        payload = _payload(conversation_id, text, previous, alternatives or _alts(state), state, [], memory_event)
        _persist(conversation_id, session_id, state, "cheaper", previous.get("id"))
        return payload
    if chosen is None:
        payload = _payload(conversation_id, compose_reply(kind="empty"), None, [], state, [], memory_event)
        _persist(conversation_id, session_id, state, "shown", None)
        return payload
    kind = _kind(update, state, memories, previous, chosen)
    return _finish(conversation_id, session_id, state, previous, chosen, alternatives, kind, memory_event, plan)


def list_memories(session_id: str) -> list[dict[str, Any]]:
    from .taste_consolidator import list_taste

    return list_taste(session_id)


def forget_memory(session_id: str, memory_id: str) -> dict[str, Any]:
    execute(
        "UPDATE preference_memories SET enabled=0, updated_at=? WHERE session_id=? AND id=?",
        (now_iso(), session_id, memory_id),
    )
    return {"id": memory_id, "enabled": False}


def memory_enabled(session_id: str) -> bool:
    row = one("SELECT memory_enabled FROM shopping_settings WHERE session_id=?", (session_id,))
    if not row:
        return True
    return bool(row["memory_enabled"])


def set_memory_enabled(session_id: str, enabled: bool) -> dict[str, Any]:
    ensure_session(session_id)
    execute(
        "INSERT INTO shopping_settings(session_id, memory_enabled, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(session_id) DO UPDATE SET memory_enabled=excluded.memory_enabled, updated_at=excluded.updated_at",
        (session_id, 1 if enabled else 0, now_iso()),
    )
    return {"memory_enabled": enabled}


def save_pick(session_id: str, conversation_id: str | None, product_id: str, reason: str) -> dict[str, Any]:
    ensure_session(session_id)
    product = get_product(product_id)
    if not product:
        return {"saved": False, "reason": "Product was not found in the catalog."}
    price = (product.get("sourceFields") or {}).get("price")
    pick_id = f"pick-{secrets.token_hex(6)}"
    execute(
        "INSERT INTO saved_picks(id, session_id, product_id, conversation_id, reason, title, price, created_at) "
        "VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(session_id, product_id) DO UPDATE SET reason=excluded.reason, conversation_id=excluded.conversation_id, title=excluded.title, price=excluded.price",
        (pick_id, session_id, product_id, conversation_id, reason, product.get("name"), price, now_iso()),
    )
    _event(session_id, conversation_id, product_id, "saved")
    return {"saved": True, "product_id": product_id, "title": product.get("name"), "reason": reason}


def list_saved(session_id: str) -> list[dict[str, Any]]:
    rows = query("SELECT * FROM saved_picks WHERE session_id=? ORDER BY created_at DESC", (session_id,))
    items = []
    for row in rows:
        product = get_product(row["product_id"])
        items.append({
            "id": row["id"],
            "product_id": row["product_id"],
            "conversation_id": row["conversation_id"],
            "reason": row["reason"],
            "title": row["title"],
            "price": row["price"],
            "created_at": row["created_at"],
            "product": product,
        })
    return items


def conversations_for_product(session_id: str, product_id: str) -> list[dict[str, Any]]:
    rows = query(
        "SELECT c.id, c.title, c.updated_at FROM conversation_products p "
        "JOIN picki_conversations c ON c.id = p.conversation_id "
        "WHERE p.session_id=? AND p.product_id=? ORDER BY c.updated_at DESC",
        (session_id, product_id),
    )
    return [{"id": row["id"], "title": row["title"], "updated_at": row["updated_at"]} for row in rows]


def conversations_for_products(session_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
    unique = list(dict.fromkeys(item for item in product_ids if item))
    if not unique:
        return []
    placeholders = ",".join("?" for _ in unique)
    rows = query(
        f"SELECT c.id, c.title, c.state_json, c.updated_at, COUNT(DISTINCT p.product_id) AS related_product_count "
        f"FROM conversation_products p JOIN picki_conversations c ON c.id=p.conversation_id AND c.session_id=p.session_id "
        f"WHERE p.session_id=? AND p.product_id IN ({placeholders}) "
        f"GROUP BY c.id, c.title, c.state_json, c.updated_at ORDER BY c.updated_at DESC, related_product_count DESC",
        (session_id, *unique),
    )
    return [{
        "id": row["id"],
        "title": row["title"],
        "updated_at": row["updated_at"],
        "related_product_count": int(row["related_product_count"]),
    } for row in rows if not decode_json(row.get("state_json"), {}).get("archivedAt")]


def create_comparison(session_id: str, product_ids: list[str]) -> dict[str, Any]:
    from fastapi import HTTPException

    from .shopping_compare import explain_comparison, snapshot

    unique = list(dict.fromkeys(item for item in product_ids if item))
    if len(unique) < 2 or len(unique) > 4:
        raise HTTPException(status_code=400, detail="Select 2 to 4 products to compare.")
    products = [item for item in (get_product(product_id) for product_id in unique) if item]
    if len(products) < 2:
        raise HTTPException(status_code=400, detail="A selected product is not available in the current catalog.")
    context = _session_compare_context(session_id, products)
    enabled = memory_enabled(session_id)
    if enabled:
        from .taste_retriever import retrieve_for_task

        retrieved_taste = retrieve_for_task(
            session_id,
            category_hint=context.get("category_hint"),
            message="Compare candidates in My Picks",
            session_context=context,
        )
    else:
        retrieved_taste = {"global": [], "category_specific": [], "session_constraints": {}, "priority_labels": []}
    explained = explain_comparison(
        products,
        shopping_context=context,
        retrieved_taste=retrieved_taste,
        memory_enabled=enabled,
    )
    winner_id, verdict = explained.get("winner_product_id"), explained["verdict"]
    shots = [snapshot(item) for item in products]
    names = " vs ".join(str(item.get("name") or item.get("id"))[:28] for item in products[:3])
    comparison_id = f"cmp-{secrets.token_hex(6)}"
    ts = now_iso()
    payload = {"snapshots": shots, "explanation": explained}
    execute(
        "INSERT INTO comparisons(id, session_id, title, verdict, winner_product_id, conversation_id, products_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (comparison_id, session_id, names, verdict, winner_id, None, encode_json(payload), ts),
    )
    return _comparison_row({
        "id": comparison_id,
        "title": names,
        "verdict": verdict,
        "winner_product_id": winner_id,
        "conversation_id": None,
        "products_json": encode_json(payload),
        "created_at": ts,
    })


def list_comparisons(session_id: str) -> list[dict[str, Any]]:
    rows = query("SELECT * FROM comparisons WHERE session_id=? ORDER BY created_at DESC", (session_id,))
    return [_comparison_row(row) for row in rows]


def link_comparison(session_id: str, comparison_id: str, conversation_id: str) -> dict[str, Any]:
    from fastapi import HTTPException

    row = one("SELECT * FROM comparisons WHERE id=? AND session_id=?", (comparison_id, session_id))
    if not row:
        raise HTTPException(status_code=404, detail="This comparison could not be found.")
    execute("UPDATE comparisons SET conversation_id=? WHERE id=? AND session_id=?", (conversation_id, comparison_id, session_id))
    payload = decode_json(row.get("products_json"), {})
    product_ids = [str(item.get("product_id")) for item in (payload.get("snapshots") or []) if item.get("product_id")]
    if product_ids:
        from .conversation_context import load_context, save_context

        context = load_context(conversation_id, session_id)
        context["focus_product_ids"] = product_ids[:4]
        context["compared_product_ids"] = product_ids[:4]
        context["focused_product_id"] = row.get("winner_product_id") or product_ids[0]
        context["shopping_goal"] = "compare"
        save_context(conversation_id, session_id, context)
        for product_id in product_ids:
            execute(
                "INSERT OR IGNORE INTO conversation_products(conversation_id,session_id,product_id,created_at) VALUES(?,?,?,?)",
                (conversation_id, session_id, product_id, now_iso()),
            )
    row["conversation_id"] = conversation_id
    return _comparison_row(row)


def _session_compare_context(session_id: str, products: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from .shopping_compare import relevant_compare_context

    product_ids = [str(item.get("id")) for item in (products or []) if item.get("id")]
    linked: set[str] = set()
    if product_ids:
        placeholders = ",".join("?" * len(product_ids))
        for row in query(
            f"SELECT conversation_id FROM conversation_products WHERE session_id=? AND product_id IN ({placeholders})",
            (session_id, *product_ids),
        ):
            if row.get("conversation_id"):
                linked.add(str(row["conversation_id"]))
        for row in query(
            f"SELECT p.conversation_id FROM cart_item_provenance p "
            f"JOIN cart_items c ON c.id = p.cart_item_id "
            f"WHERE c.session_id=? AND c.product_id IN ({placeholders}) AND p.conversation_id IS NOT NULL",
            (session_id, *product_ids),
        ):
            linked.add(str(row["conversation_id"]))
        for row in query(
            f"SELECT conversation_id FROM saved_picks WHERE session_id=? AND product_id IN ({placeholders}) AND conversation_id IS NOT NULL",
            (session_id, *product_ids),
        ):
            linked.add(str(row["conversation_id"]))

    conversations: list[dict[str, Any]] = []
    for row in query("SELECT id, title, state_json FROM picki_conversations WHERE session_id=?", (session_id,)):
        ctx_row = one("SELECT context_json FROM conversation_context WHERE conversation_id=?", (row["id"],))
        data = decode_json(ctx_row.get("context_json") if ctx_row else None, {})
        state = decode_json(row.get("state_json"), {})
        if not isinstance(data, dict):
            data = {}
        if not isinstance(state, dict):
            state = {}
        conversations.append({
            "id": row["id"],
            "title": row.get("title") or "",
            "need": state.get("need") or "",
            "requirements": data.get("requirements") or [],
            "devices": data.get("devices") or [],
            "use_cases": data.get("use_cases") or [],
            "goal": data.get("current_priority_override") or state.get("goal"),
            "category_hint": data.get("category_hint"),
            "linked": row["id"] in linked,
        })
    return relevant_compare_context(products or [], conversations)


def _comparison_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = decode_json(row.get("products_json"), [])
    products = raw
    explanation = None
    if isinstance(raw, dict):
        products = raw.get("snapshots") or raw.get("products") or []
        explanation = raw.get("explanation")
    return {
        "id": row["id"],
        "title": row["title"],
        "verdict": row["verdict"],
        "winner_product_id": row.get("winner_product_id"),
        "conversation_id": row.get("conversation_id"),
        "products": products,
        "explanation": explanation,
        "created_at": row["created_at"],
    }


def add_note_memory(session_id: str, label: str) -> dict[str, Any]:
    ensure_session(session_id)
    text = label.strip()[:100]
    if not text or not memory_enabled(session_id):
        return {"saved": False}
    candidate = memory_candidate(interpret(text, "message", blank_session()))
    if candidate:
        existing = one(
            "SELECT id, label FROM preference_memories WHERE session_id=? AND facet=? AND value=? AND enabled=1",
            (session_id, candidate["facet"], candidate["value"]),
        )
        if existing:
            return {"id": existing["id"], "label": existing["label"], "saved": False}
        memory_id = f"mem-{secrets.token_hex(6)}"
        ts = now_iso()
        execute(
            "INSERT INTO preference_memories(id, session_id, facet, value, label, scope, confidence, evidence, source, enabled, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,1,?,?)",
            (memory_id, session_id, candidate["facet"], candidate["value"], candidate["label"], candidate["scope"], 0.9, text, "explicit", ts, ts),
        )
        return {"id": memory_id, "label": candidate["label"], "saved": True}
    existing = one(
        "SELECT id FROM preference_memories WHERE session_id=? AND facet='note' AND label=? AND enabled=1",
        (session_id, text),
    )
    if existing:
        return {"id": existing["id"], "label": text, "saved": False}
    memory_id = f"mem-{secrets.token_hex(6)}"
    ts = now_iso()
    execute(
        "INSERT INTO preference_memories(id, session_id, facet, value, label, scope, confidence, evidence, source, enabled, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,1,?,?)",
        (memory_id, session_id, "note", text, text, "personal", 0.9, "Added in My Taste", "explicit", ts, ts),
    )
    return {"id": memory_id, "label": text, "saved": True}


def list_cart(session_id: str) -> list[dict[str, Any]]:
    rows = query(
        "SELECT c.id, c.product_id, c.created_at, "
        "(SELECT conversation_id FROM cart_item_provenance WHERE cart_item_id=c.id AND conversation_id IS NOT NULL ORDER BY created_at DESC LIMIT 1) AS conversation_id, "
        "(SELECT source_type FROM cart_item_provenance WHERE cart_item_id=c.id ORDER BY created_at DESC LIMIT 1) AS source_type "
        "FROM cart_items c WHERE c.session_id=? ORDER BY c.created_at DESC",
        (session_id,),
    )
    items = []
    seen: set[str] = set()
    for row in rows:
        if row["product_id"] in seen:
            continue
        seen.add(row["product_id"])
        product = get_product(row["product_id"])
        price = None if not product else (product.get("sourceFields") or {}).get("price")
        items.append({
            "id": row["id"],
            "product_id": row["product_id"],
            "conversation_id": row["conversation_id"],
            "source_type": row["source_type"] or "product",
            "created_at": row["created_at"],
            "title": product.get("name") if product else row["product_id"],
            "price": price,
            "product": product,
        })
    return items


def add_cart_item(session_id: str, product_id: str, conversation_id: str | None, source_type: str) -> dict[str, Any]:
    ensure_session(session_id)
    product = get_product(product_id)
    if not product:
        return {"saved": False, "reason": "Product was not found in the catalog."}
    existing = one("SELECT id FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product_id))
    cart_id = existing["id"] if existing else f"cart-{secrets.token_hex(6)}"
    if not existing:
        execute(
            "INSERT INTO cart_items(id, session_id, product_id, created_at) VALUES(?,?,?,?)",
            (cart_id, session_id, product_id, now_iso()),
        )
    linked_conversation = conversation_id if source_type == "chat" and conversation_id else None
    execute(
        "INSERT INTO cart_item_provenance(id, cart_item_id, conversation_id, source_type, created_at) VALUES(?,?,?,?,?)",
        (f"prov-{secrets.token_hex(6)}", cart_id, linked_conversation, source_type or "product", now_iso()),
    )
    _event(session_id, linked_conversation, product_id, "saved")
    return {"saved": True, "id": cart_id, "product_id": product_id, "already": bool(existing)}


def remove_cart_item(session_id: str, product_id: str) -> dict[str, Any]:
    row = one("SELECT id FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product_id))
    if row:
        execute("DELETE FROM cart_item_provenance WHERE cart_item_id=?", (row["id"],))
        execute("DELETE FROM cart_items WHERE id=?", (row["id"],))
    return {"removed": product_id}


def remove_saved(session_id: str, product_id: str) -> dict[str, Any]:
    execute("DELETE FROM saved_picks WHERE session_id=? AND product_id=?", (session_id, product_id))
    return {"removed": product_id}


def load_session(conversation_id: str, session_id: str) -> dict[str, Any]:
    row = one("SELECT state_json FROM shopping_sessions WHERE conversation_id=?", (conversation_id,))
    if not row:
        return blank_session()
    state = decode_json(row["state_json"], {})
    if not isinstance(state, dict):
        return blank_session()
    return {**blank_session(), **state, "session_id": session_id}


def _finish(conversation_id: str, session_id: str, state: dict[str, Any], previous: dict[str, Any] | None, chosen: dict[str, Any], alternatives: list[dict[str, Any]], kind: str, memory_event: dict[str, Any] | None, plan: dict[str, Any]) -> dict[str, Any]:
    saved = price_delta(previous, chosen) if kind == "cheaper" else None
    tradeoff = evidenced_tradeoff(previous, chosen) if previous and previous.get("id") != chosen.get("id") else None
    cleaner = looks_cleaner(previous, chosen)
    remembered = None
    if kind == "remembered":
        remembered = _remembered_phrase(memories_for_phrase(session_id, state))
        state["memory_mentioned"] = True
    text = compose_reply(kind=kind, saved_amount=saved, tradeoff=tradeoff, cleaner=cleaner, remembered_label=remembered, why=_compare_line(chosen, alternatives[0]) if kind == "compare" else None)
    if previous and previous.get("id") != chosen.get("id"):
        rejected = list(state.get("rejected_product_ids") or [])
        rejected.append(previous["id"])
        state["rejected_product_ids"] = list(dict.fromkeys(rejected))[-12:]
    state["current_product_id"] = chosen.get("id")
    state["alternative_ids"] = [item.get("id") for item in alternatives if item.get("id")]
    changes = _changes(previous, chosen)
    event = "shown" if not previous or previous.get("id") == chosen.get("id") else kind
    payload = _payload(conversation_id, text, chosen, alternatives, state, changes, memory_event, apply_personal=bool(plan.get("apply_personal", True)))
    _persist(conversation_id, session_id, state, event if event in {"cheaper", "style", "shown", "focus"} else "shown", chosen.get("id"))
    return payload


def _compare(conversation_id: str, session_id: str, state: dict[str, Any], previous: dict[str, Any] | None, memory_event: dict[str, Any] | None) -> dict[str, Any]:
    alts = _alts(state)
    if not previous or not alts:
        text = compose_reply(kind="compare", why="I only have one solid match right now. Ask for a cheaper option or a different vibe.")
    else:
        text = compose_reply(kind="compare", why=_compare_line(previous, alts[0]))
    payload = _payload(conversation_id, text, previous, alts, state, [], memory_event)
    _persist(conversation_id, session_id, state, "compared", previous.get("id") if previous else None)
    return payload


def _payload(conversation_id: str, message: str, primary: dict[str, Any] | None, alternatives: list[dict[str, Any]], state: dict[str, Any], changes: list[str], memory_event: dict[str, Any] | None, apply_personal: bool = True) -> dict[str, Any]:
    style = state.get("style") if apply_personal and state.get("recipient") != "gift" else None
    budget = state.get("budget_max")
    return {
        "conversation_id": conversation_id,
        "message": message,
        "active_pick": card(primary, budget, style) if primary else None,
        "alternatives": [card(item, budget, style) for item in alternatives[:2]],
        "quick_actions": ["cheaper", "different_style", "compare", "why_this"] if primary else [],
        "changed_since_last_pick": changes,
        "memory_event": memory_event,
    }


def _kind(update: dict[str, Any], state: dict[str, Any], memories: list[dict[str, Any]], previous: dict[str, Any] | None, chosen: dict[str, Any]) -> str:
    if update["rerank"] == "focus":
        return "focus"
    if update["rerank"] == "cheaper" and previous and previous.get("id") != chosen.get("id"):
        return "cheaper"
    if update["rerank"] == "style" and previous and previous.get("id") != chosen.get("id"):
        return "style"
    personal = [item for item in memories if item.get("scope") == "personal" and item.get("facet") == "style"]
    if not previous and personal and state.get("recipient") != "gift" and not state.get("memory_mentioned"):
        return "remembered"
    if state.get("budget_max") is None and not previous:
        return "first_open"
    return "first"


def memories_for_phrase(session_id: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("recipient") == "gift" or not memory_enabled(session_id):
        return []
    return list_memories(session_id)


def _remembered_phrase(memories: list[dict[str, Any]]) -> str:
    for item in memories:
        if item.get("value") == "minimal":
            return "clean designs"
        if item.get("value") == "bold":
            return "bolder designs"
        if item.get("value") == "value":
            return "good value"
    return "clean designs"


def _compare_line(primary: dict[str, Any], other: dict[str, Any]) -> str:
    left = _safe_price(primary)
    right = _safe_price(other)
    if left is not None and right is not None and left != right:
        cheaper = "less" if left < right else "more"
        return f"This pick costs {_money(abs(left - right))} {cheaper} than the other option. {why_for_you(primary, None, None)}"
    return why_for_you(primary, None, None)


def _changes(previous: dict[str, Any] | None, chosen: dict[str, Any]) -> list[str]:
    if not previous or previous.get("id") == chosen.get("id"):
        return []
    lines = []
    delta = price_delta(previous, chosen)
    if delta:
        lines.append(f"Saves {_money(delta)}")
    if (previous.get("brand") or "") != (chosen.get("brand") or ""):
        lines.append("Different brand")
    return lines


def _alts(state: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for product_id in state.get("alternative_ids") or []:
        product = get_product(product_id)
        if product:
            found.append(product)
    return found


def _caution(product: dict[str, Any]) -> str:
    from .shopping_intent import one_caution
    return one_caution(product)


def maybe_store_memory(session_id: str, message: str, update: dict[str, Any]) -> dict[str, Any] | None:
    candidate = memory_candidate(update)
    if not candidate or not memory_enabled(session_id):
        return None
    existing = one(
        "SELECT id, label FROM preference_memories WHERE session_id=? AND facet=? AND value=? AND enabled=1",
        (session_id, candidate["facet"], candidate["value"]),
    )
    if existing:
        return None
    memory_id = f"mem-{secrets.token_hex(6)}"
    ts = now_iso()
    execute(
        "INSERT INTO preference_memories(id, session_id, facet, value, label, scope, confidence, evidence, source, enabled, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,1,?,?)",
        (memory_id, session_id, candidate["facet"], candidate["value"], candidate["label"], candidate["scope"], 0.86, message[:240], "explicit", ts, ts),
    )
    return {"id": memory_id, "label": candidate["label"]}


def _persist(conversation_id: str, session_id: str, state: dict[str, Any], event_type: str, product_id: str | None) -> None:
    execute(
        "INSERT INTO shopping_sessions(conversation_id, session_id, state_json, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
        (conversation_id, session_id, encode_json(state), now_iso()),
    )
    _event(session_id, conversation_id, product_id, event_type)
    linked = [product_id, state.get("current_product_id"), *(state.get("alternative_ids") or [])]
    seen: set[str] = set()
    ts = now_iso()
    for item in linked:
        if not item or item in seen:
            continue
        seen.add(str(item))
        execute(
            "INSERT OR IGNORE INTO conversation_products(conversation_id, session_id, product_id, created_at) VALUES(?,?,?,?)",
            (conversation_id, session_id, str(item), ts),
        )


def _event(session_id: str, conversation_id: str | None, product_id: str | None, event_type: str) -> None:
    execute(
        "INSERT INTO interaction_events(id, session_id, conversation_id, product_id, event_type, created_at) VALUES(?,?,?,?,?,?)",
        (f"ix-{secrets.token_hex(6)}", session_id, conversation_id, product_id, event_type, now_iso()),
    )


def _memory_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "facet": row["facet"],
        "value": row["value"],
        "label": row["label"],
        "scope": row["scope"],
        "source": row["source"],
        "evidence": row["evidence"],
        "enabled": bool(row["enabled"]),
        "updated_at": row["updated_at"],
    }


def _safe_price(product: dict[str, Any] | None) -> float | None:
    if not product:
        return None
    source = (product.get("sourceFields") or {}).get("price")
    try:
        amount = float(source)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _money(amount: float) -> str:
    if abs(amount - round(amount)) < 0.001:
        return f"${amount:.0f}"
    return f"${amount:.2f}"
