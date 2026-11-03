from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..services import events as event_service
from ..services import products as product_service
from ..services.profile import ensure_profile


@dataclass
class ToolCall:
    tool_name: str
    input_summary: str
    output_summary: str
    latency: float
    success: bool
    error: str | None = None


class PickMateTool:
    name = "tool"

    async def execute(self, input: dict[str, Any]) -> Any:
        raise NotImplementedError


class ProductTool(PickMateTool):
    name = "ProductTool"

    async def execute(self, input: dict[str, Any]) -> list[dict[str, Any]]:
        product_ids = input.get("product_ids") or None
        if product_ids:
            return product_service.get_products(product_ids)
        query = input.get("query")
        category = input.get("category")
        return product_service.repository.search_products(
            query or "home audio",
            category,
            input.get("max_price"),
        )


class PriceTool(PickMateTool):
    name = "PriceTool"

    async def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        product_id = input["product_id"]
        history = product_service.price_history(product_id)
        if len(history) < 4:
            return {"status": "insufficient", "current_price": None, "average_30d": None, "average_90d": None, "lowest_90d": None, "highest_90d": None, "current_vs_avg": None, "current_vs_low": None}
        prices = [p["price"] for p in history]
        current = prices[-1]
        last30 = prices[-5:]
        avg30 = round(sum(last30) / len(last30))
        avg90 = round(sum(prices) / len(prices))
        low = min(prices)
        high = max(prices)
        current_vs_avg = current - avg90
        current_vs_low = current - low
        if current_vs_low <= 12:
            status = "near_low"
        elif current_vs_avg <= -20:
            status = "good"
        elif current_vs_avg > 60:
            status = "high"
        else:
            status = "normal"
        return {
            "status": status,
            "current_price": current,
            "average_30d": avg30,
            "average_90d": avg90,
            "lowest_90d": low,
            "highest_90d": high,
            "current_vs_avg": current_vs_avg,
            "current_vs_low": current_vs_low,
            "history": history,
        }


class ReviewEvidenceTool(PickMateTool):
    name = "ReviewEvidenceTool"

    async def execute(self, input: dict[str, Any]) -> list[dict[str, Any]]:
        product_id = input["product_id"]
        reviews = product_service.review_evidence(product_id)[:8]
        discussions = product_service.discussion_evidence(product_id)
        return reviews + discussions


class VideoEvidenceTool(PickMateTool):
    name = "VideoEvidenceTool"

    async def execute(self, input: dict[str, Any]) -> list[dict[str, Any]]:
        return product_service.video_evidence(input["product_id"])


class ProfileTool(PickMateTool):
    name = "ProfileTool"

    async def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        return ensure_profile(input["session_id"])


class BrowsingContextTool(PickMateTool):
    name = "BrowsingContextTool"

    async def execute(self, input: dict[str, Any]) -> list[dict[str, Any]]:
        return event_service.session_events(input["session_id"])


class ToolRegistry:
    def __init__(self) -> None:
        self.tools = {
            tool.name: tool
            for tool in [ProductTool(), PriceTool(), ReviewEvidenceTool(), VideoEvidenceTool(), ProfileTool(), BrowsingContextTool()]
        }

    async def call(self, name: str, input: dict[str, Any], calls: list[dict[str, Any]]) -> Any:
        started = time.perf_counter()
        try:
            result = await self.tools[name].execute(input)
            summary = summarize(result)
            calls.append(ToolCall(name, summarize(input), summary, time.perf_counter() - started, True). __dict__)
            return result
        except Exception as exc:
            calls.append(ToolCall(name, summarize(input), "", time.perf_counter() - started, False, str(exc)).__dict__)
            return None


def summarize(value: Any) -> str:
    if isinstance(value, list):
        return f"{len(value)} items"
    if isinstance(value, dict):
        keys = list(value.keys())[:6]
        return f"keys={keys}"
    return str(value)[:120]
