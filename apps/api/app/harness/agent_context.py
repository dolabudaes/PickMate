from __future__ import annotations

from typing import Any

def build_agent_context(
    session_id: str,
    conversation_id: str,
    message: str,
    product_id: str | None,
    cart_snapshot: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from ..services import shopping_loop as shopping

    state = shopping.load_session(conversation_id, session_id)
    focus_ids = []
    if product_id:
        focus_ids.append(product_id)
    if state.get("current_product_id"):
        focus_ids.append(state["current_product_id"])
    focus_ids.extend(state.get("alternative_ids") or [])
    focus_ids = list(dict.fromkeys(item for item in focus_ids if item))[:6]
    return {
        "session_id": session_id,
        "conversation_id": conversation_id,
        "user_message": message.strip(),
        "focus_product_ids": focus_ids,
        "shopping_intent": {
            "budget_max": state.get("budget_max"),
            "style": state.get("style"),
            "recipient": state.get("recipient"),
            "rejected_product_ids": (state.get("rejected_product_ids") or [])[-6:],
        },
        "cart_count": len(cart_snapshot or []),
    }


def planner_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    intent = context.get("shopping_intent") or {}
    product_intent = context.get("product_intent")
    intent_kind = getattr(product_intent, "kind", None) if product_intent else None
    session_ctx = context.get("session_context") or {}
    return [
        {
            "role": "system",
            "content": (
                "You are Picki, a shopping decision agent. Use tools to fetch catalog facts on demand. "
                "Never invent specifications, review counts, certifications, or live prices. "
                "Cart and preference mutations must use propose_* tools only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User message: {context.get('user_message')}\n"
                f"Focus product ids: {', '.join(context.get('focus_product_ids') or []) or 'none'}\n"
                f"Intent budget_max={intent.get('budget_max')} style={intent.get('style')} recipient={intent.get('recipient')}\n"
                f"Product category intent: {intent_kind or 'unknown'} "
                f"session_budget={session_ctx.get('session_budget_max')} category_hint={session_ctx.get('category_hint')}\n"
                f"Cart items: {context.get('cart_count')}"
            ),
        },
    ]
