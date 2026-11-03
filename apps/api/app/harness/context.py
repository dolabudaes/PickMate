from __future__ import annotations

from collections import Counter
from typing import Any

from .intent import extract_budget
from .tools import ToolRegistry


class ContextBuilder:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def build(self, request: Any, intent_type: str, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
        profile = await self.tools.call("ProfileTool", {"session_id": request.session_id}, tool_calls) or {}
        events = await self.tools.call("BrowsingContextTool", {"session_id": request.session_id}, tool_calls) or []
        viewed = [e["product_id"] for e in events if e.get("product_id") and e["name"] == "product_viewed"]
        recent_viewed = list(dict.fromkeys(reversed(viewed)))[:5]
        compared = [e["product_id"] for e in events if e.get("product_id") and e["name"] == "product_added_to_compare"]
        compared = list(dict.fromkeys(compared))[-3:]
        repeated = [pid for pid, count in Counter(viewed).items() if count >= 2]
        evidence_opened = [e for e in events if str(e["name"]).endswith("_opened")]

        candidate_ids = list(request.candidate_product_ids)
        if not candidate_ids and intent_type in {"PRODUCT_COMPARISON", "PRODUCT_DECISION"}:
            candidate_ids = compared or recent_viewed[:3]
        if not candidate_ids and request.current_product_id and intent_type in {"PRICE_CHECK", "PRODUCT_RISK_QUERY", "GENERAL_PRODUCT_QUESTION"}:
            candidate_ids = [request.current_product_id]
        selected_ids = list(dict.fromkeys([*(candidate_ids or []), *(recent_viewed if not candidate_ids else []), *repeated]))[:8]
        products = await self.tools.call(
            "ProductTool",
            {
                "product_ids": selected_ids or None,
                "query": request.message if not selected_ids else None,
                "max_price": request.max_price if getattr(request, "max_price", None) is not None else extract_budget(request.message or ""),
            },
            tool_calls,
        ) or []
        if request.current_product_id and not any(p["id"] == request.current_product_id for p in products):
            products = (await self.tools.call("ProductTool", {"product_ids": [request.current_product_id]}, tool_calls) or []) + products

        return {
            "profile": profile,
            "events": events,
            "current_product_id": request.current_product_id,
            "recent_product_ids": recent_viewed,
            "compared_product_ids": compared,
            "repeated_product_ids": repeated,
            "opened_evidence_types": list(dict.fromkeys(str(e["name"]).replace("_opened", "") for e in evidence_opened)),
            "candidate_product_ids": selected_ids,
            "products": products,
        }
