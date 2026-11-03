from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..db import decode_json, one
from .conversation_context import load_context, save_context
from .shopping_intent import blank_session

FIRST_REF = re.compile(r"\b(the )?first (one|option|pick|cable|product)\b", re.I)
SECOND_REF = re.compile(r"\b(the )?second (one|option|pick|cable|product)\b", re.I)
THIRD_REF = re.compile(r"\b(the )?third (one|option|pick|product)\b", re.I)
OTHER_REF = re.compile(r"\b(the other one|what about the other)\b", re.I)
THOSE_TWO = re.compile(r"\b(those two|both of them|the two|compare (those|them|these two)|these two)\b|(?:比较|对比)(?:这|那)?两(?:件|个|款)", re.I)
THIS_THAT = re.compile(r"\b(this one|that one|this cable|that cable)\b", re.I)
PICK_YOU = re.compile(r"\b(the one you('d| would) pick|your pick|the one you('d| would) (choose|recommend))\b", re.I)
REMOVE_CONSTRAINT = re.compile(r"\b(don'?t need|no longer need|remove|drop|without)\b.{0,40}\b(4k|120|hz|hdmi|arc|budget)\b", re.I)


@dataclass
class ShoppingConversationState:
    conversation_id: str
    anchor_product_id: str | None = None
    focused_product_id: str | None = None
    compared_product_ids: list[str] = field(default_factory=list)
    shopping_goal: str | None = None
    hard_constraints: list[str] = field(default_factory=list)
    soft_constraints: list[str] = field(default_factory=list)
    rejected_product_ids: list[str] = field(default_factory=list)
    rejection_reasons: dict[str, str] = field(default_factory=dict)
    current_budget: float | None = None
    conversation_summary: str | None = None
    turn_log: list[dict[str, Any]] = field(default_factory=list)
    shown_product_ids: list[str] = field(default_factory=list)
    listed_product_ids: list[str] = field(default_factory=list)
    pending_clarification: dict[str, Any] | None = None
    decision_product_id: str | None = None
    last_constraint_changes: list[str] = field(default_factory=list)
    category: str | None = None

    def to_context_patch(self) -> dict[str, Any]:
        return {
            "anchor_product_id": self.anchor_product_id,
            "focused_product_id": self.focused_product_id,
            "compared_product_ids": self.compared_product_ids,
            "shopping_goal": self.shopping_goal,
            "hard_constraints": self.hard_constraints,
            "soft_constraints": self.soft_constraints,
            "rejected_product_ids": self.rejected_product_ids,
            "rejection_reasons": self.rejection_reasons,
            "conversation_summary": self.conversation_summary,
            "turn_log": self.turn_log[-12:],
            "shown_product_ids": self.shown_product_ids,
            "listed_product_ids": self.listed_product_ids,
            "pending_clarification": self.pending_clarification,
            "decision_product_id": self.decision_product_id,
            "last_constraint_changes": self.last_constraint_changes,
            "category": self.category,
        }


def load_shopping_state(conversation_id: str, session_id: str) -> ShoppingConversationState:
    ctx = load_context(conversation_id, session_id)
    shop = _load_shopping_session(conversation_id, session_id)
    hard = list(dict.fromkeys([*(ctx.get("requirements") or []), *(ctx.get("hard_constraints") or [])]))
    rejected = list(dict.fromkeys([*(ctx.get("rejected_product_ids") or []), *(shop.get("rejected_product_ids") or [])]))
    focus = ctx.get("focused_product_id") or shop.get("current_product_id") or _first(ctx.get("focus_product_ids"))
    anchor = ctx.get("anchor_product_id") or _first(ctx.get("focus_product_ids")) or focus
    compared = list(ctx.get("compared_product_ids") or [])
    if not compared and len(shop.get("alternative_ids") or []) >= 2:
        compared = list(shop["alternative_ids"][:2])
    budget = ctx.get("session_budget_max") or shop.get("budget_max")
    shown = list(ctx.get("shown_product_ids") or [])
    if not shown:
        shown = [x for x in [focus, *(shop.get("alternative_ids") or [])] if x]
    listed = list(ctx.get("listed_product_ids") or [])
    if not listed and len(shown) >= 2:
        listed = shown[:4]
    return ShoppingConversationState(
        conversation_id=conversation_id,
        anchor_product_id=anchor,
        focused_product_id=focus,
        compared_product_ids=compared,
        shopping_goal=ctx.get("shopping_goal"),
        hard_constraints=hard,
        soft_constraints=list(ctx.get("soft_constraints") or []),
        rejected_product_ids=rejected,
        rejection_reasons=dict(ctx.get("rejection_reasons") or {}),
        current_budget=float(budget) if budget is not None else None,
        conversation_summary=ctx.get("conversation_summary"),
        turn_log=list(ctx.get("turn_log") or []),
        shown_product_ids=shown,
        listed_product_ids=listed,
        pending_clarification=ctx.get("pending_clarification"),
        decision_product_id=ctx.get("decision_product_id") or focus,
        last_constraint_changes=list(ctx.get("last_constraint_changes") or []),
        category=ctx.get("category") or ctx.get("category_hint"),
    )


def recent_messages(state: ShoppingConversationState, limit: int = 8) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in state.turn_log[-limit:]:
        role = item.get("role") or "user"
        text = (item.get("text") or "").strip()
        if text:
            out.append({"role": role, "text": text[:500]})
    return out


def append_turn(
    conversation_id: str,
    session_id: str,
    *,
    user_message: str,
    assistant_message: str,
    product_id: str | None,
    focused_product_id: str | None,
    alternative_ids: list[str],
) -> None:
    ctx = load_context(conversation_id, session_id)
    log = list(ctx.get("turn_log") or [])
    log.append({"role": "user", "text": user_message[:600], "product_id": product_id})
    if assistant_message:
        log.append({"role": "assistant", "text": assistant_message[:800], "product_id": focused_product_id})
    ctx["turn_log"] = log[-20:]
    if product_id and not ctx.get("anchor_product_id"):
        ctx["anchor_product_id"] = product_id
    if focused_product_id:
        ctx["focused_product_id"] = focused_product_id
    ids = list(dict.fromkeys([*(ctx.get("focus_product_ids") or []), *( [product_id] if product_id else []), focused_product_id or ""]))
    ctx["focus_product_ids"] = [x for x in ids if x][:6]
    if len(alternative_ids) >= 2:
        ctx["compared_product_ids"] = alternative_ids[:4]
    shown = list(dict.fromkeys([x for x in [focused_product_id, *alternative_ids] if x]))
    if shown:
        ctx["shown_product_ids"] = shown[:6]
        if len(shown) >= 2:
            ctx["listed_product_ids"] = shown[:4]
        if not ctx.get("anchor_product_id"):
            ctx["anchor_product_id"] = shown[0]
        ctx["decision_product_id"] = focused_product_id or shown[0]
    save_context(conversation_id, session_id, ctx)


def apply_interpretation_to_state(
    conversation_id: str,
    session_id: str,
    interpretation: Any,
    message: str,
) -> ShoppingConversationState:
    from .picki_assist import TurnInterpretation

    state = load_shopping_state(conversation_id, session_id)
    ctx = load_context(conversation_id, session_id)
    if not isinstance(interpretation, TurnInterpretation):
        return state
    if interpretation.reference_product_ids:
        state.focused_product_id = interpretation.reference_product_ids[0]
        if not state.anchor_product_id:
            state.anchor_product_id = interpretation.reference_product_ids[0]
    if interpretation.turn_goal:
        state.shopping_goal = interpretation.turn_goal
        ctx["shopping_goal"] = interpretation.turn_goal
    priority_override = ctx.get("current_priority_override")
    incoming_hard = list(interpretation.hard_constraints or [])
    if priority_override == "refresh_60":
        state.hard_constraints = [item for item in state.hard_constraints if "120" not in item]
        incoming_hard = [item for item in incoming_hard if "120" not in item]
    elif priority_override == "refresh_120":
        state.hard_constraints = [item for item in state.hard_constraints if "60" not in item or "120" in item]
        incoming_hard = [item for item in incoming_hard if "60" not in item or "120" in item]
    if incoming_hard:
        state.hard_constraints = list(dict.fromkeys([*state.hard_constraints, *incoming_hard]))
        ctx["requirements"] = state.hard_constraints
        ctx["hard_constraints"] = state.hard_constraints
    if interpretation.soft_preferences:
        state.soft_constraints = list(dict.fromkeys([*state.soft_constraints, *interpretation.soft_preferences]))
        ctx["soft_constraints"] = state.soft_constraints
    removed = getattr(interpretation, "removed_constraints", None) or []
    for item in removed:
        state.hard_constraints = [x for x in state.hard_constraints if item.lower() not in x.lower()]
        ctx["requirements"] = state.hard_constraints
    lower = (message or "").lower()
    if REMOVE_CONSTRAINT.search(message) or ("no longer need" in lower or "don't need" in lower):
        if "4k" in lower or "120" in lower:
            state.hard_constraints = [x for x in state.hard_constraints if "120" not in x and "4K" not in x.upper()]
            ctx["requirements"] = state.hard_constraints
    if interpretation.turn_goal == "compare" and len(interpretation.reference_product_ids) >= 2:
        state.compared_product_ids = interpretation.reference_product_ids[:4]
        ctx["compared_product_ids"] = state.compared_product_ids
    if getattr(interpretation, "clarification_needed", None):
        state.pending_clarification = {"question": interpretation.clarification_needed}
        ctx["pending_clarification"] = state.pending_clarification
    else:
        state.pending_clarification = None
        ctx["pending_clarification"] = None
    if interpretation.category_kind:
        state.category = interpretation.category_kind
        ctx["category"] = interpretation.category_kind
    if getattr(interpretation, "conversation_summary", None):
        state.conversation_summary = interpretation.conversation_summary
        ctx["conversation_summary"] = interpretation.conversation_summary
    ctx.update(state.to_context_patch())
    save_context(conversation_id, session_id, ctx)
    return load_shopping_state(conversation_id, session_id)


def resolve_product_references(
    message: str,
    *,
    product_id: str | None,
    shop_state: ShoppingConversationState,
    session_context: dict[str, Any],
) -> list[str]:
    text = (message or "").lower()
    refs: list[str] = []
    if product_id:
        refs.append(product_id)
    if shop_state.focused_product_id:
        refs.append(shop_state.focused_product_id)
    if shop_state.anchor_product_id:
        refs.append(shop_state.anchor_product_id)
    refs.extend(shop_state.compared_product_ids or [])
    refs.extend(session_context.get("focus_product_ids") or [])
    refs = list(dict.fromkeys([r for r in refs if r]))

    listed = shop_state.listed_product_ids or shop_state.shown_product_ids or shop_state.compared_product_ids
    if re.search(r"\bcompare\b", text) and FIRST_REF.search(text):
        first = shop_state.anchor_product_id or (listed[0] if listed else None)
        current = shop_state.focused_product_id or shop_state.decision_product_id
        if current and first and current != first:
            return [current, first]
        other = next((item for item in listed if item and item != (current or first)), None)
        if current and other:
            return [current, other]
        if first and other:
            return [first, other]
    if THOSE_TWO.search(text) and len(listed) >= 2:
        return listed[:2]
    if PICK_YOU.search(text) and (shop_state.decision_product_id or shop_state.focused_product_id):
        return [shop_state.decision_product_id or shop_state.focused_product_id]
    if FIRST_REF.search(text):
        first = shop_state.anchor_product_id or (listed[0] if listed else None)
        if first:
            return [first]
    if SECOND_REF.search(text) and len(listed) >= 2:
        return [listed[1]]
    if THIRD_REF.search(text) and len(listed) >= 3:
        return [listed[2]]
    if OTHER_REF.search(text):
        focus = shop_state.focused_product_id
        other = next((item for item in listed if item and item != focus), None)
        if other:
            return [other]
    if THIS_THAT.search(text) and shop_state.focused_product_id:
        return [shop_state.focused_product_id]
    if product_id:
        return [product_id, *refs][:4]
    return refs[:4]


def _load_shopping_session(conversation_id: str, session_id: str) -> dict[str, Any]:
    row = one("SELECT state_json FROM shopping_sessions WHERE conversation_id=?", (conversation_id,))
    if not row:
        return blank_session()
    state = decode_json(row["state_json"], {})
    if not isinstance(state, dict):
        return blank_session()
    return {**blank_session(), **state, "session_id": session_id}


def _first(items: list[str] | None) -> str | None:
    if not items:
        return None
    return items[0]
