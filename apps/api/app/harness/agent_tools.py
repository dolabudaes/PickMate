from __future__ import annotations

import secrets
import time
from typing import Any

from ..services import products as product_service
from ..services.shopping_compare import comparison_verdict, reference_amount, snapshot
from .tools import PriceTool, ToolRegistry


READ_ONLY_TOOLS = {
    "get_cart",
    "get_product_details",
    "get_product_reviews",
    "get_user_preferences",
    "compare_products",
    "search_products",
}

PROPOSE_TOOLS = {
    "propose_cart_update",
    "propose_preference_update",
}


def openai_tool_schemas() -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": "get_cart", "description": "Read the user's cart snapshot.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
        {
            "type": "function",
            "function": {
                "name": "get_product_details",
                "description": "Fetch verified catalog details for product ids.",
                "parameters": {
                    "type": "object",
                    "properties": {"product_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6}},
                    "required": ["product_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_product_reviews",
                "description": "Fetch customer review excerpts from the catalog.",
                "parameters": {
                    "type": "object",
                    "properties": {"product_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4}},
                    "required": ["product_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_user_preferences",
                "description": "Read confirmed My Taste preferences for this session.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_products",
                "description": "Deterministic comparison using catalog facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
                        "criteria": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["product_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_products",
                "description": "Search the product catalog.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "filters": {
                            "type": "object",
                            "properties": {
                                "max_price": {"type": "number"},
                                "category": {"type": "string"},
                            },
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_cart_update",
                "description": "Propose cart add/remove changes. Requires user confirmation before execution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "enum": ["add", "remove"]},
                                    "product_id": {"type": "string"},
                                },
                                "required": ["action", "product_id"],
                            },
                        }
                    },
                    "required": ["changes"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_preference_update",
                "description": "Propose My Taste preference updates. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "preferences": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
                    },
                    "required": ["preferences"],
                },
            },
        },
    ]


class ShoppingAgentToolRegistry:
    def __init__(self) -> None:
        self._legacy = ToolRegistry()
        self._price = PriceTool()

    @staticmethod
    def openai_tool_schemas() -> list[dict[str, Any]]:
        return openai_tool_schemas()

    async def execute(self, session_id: str, name: str, arguments: dict[str, Any]) -> Any:
        from ..services import shopping_loop as shopping

        if name == "get_cart":
            return {"items": shopping.list_cart(session_id)}
        if name == "get_product_details":
            products = product_service.get_products(arguments.get("product_ids") or [])
            return {"products": [compact_product(item) for item in products]}
        if name == "get_product_reviews":
            from ..services.review_provider import fetch_review_intelligence

            out = []
            for product_id in arguments.get("product_ids") or []:
                products = product_service.get_products([product_id])
                product = products[0] if products else {"id": product_id}
                intel = fetch_review_intelligence(product)
                out.append({
                    "product_id": product_id,
                    "reviews": intel.get("sources") or [],
                    "available": bool(intel.get("available")),
                    "summary": intel.get("summary"),
                    "provider": intel.get("provider"),
                })
            return {"items": out}
        if name == "get_user_preferences":
            if not shopping.memory_enabled(session_id):
                return {"enabled": False, "preferences": []}
            return {"enabled": True, "preferences": shopping.list_memories(session_id)}
        if name == "compare_products":
            return compare_products(arguments.get("product_ids") or [], arguments.get("criteria") or [])
        if name == "search_products":
            filters = arguments.get("filters") or {}
            rows = product_service.repository.search_products(
                arguments.get("query") or "",
                filters.get("category"),
                filters.get("max_price"),
            )
            return {"products": [compact_product(item) for item in rows[:8]]}
        if name == "propose_cart_update":
            return validate_cart_proposal(session_id, arguments.get("changes") or [])
        if name == "propose_preference_update":
            return validate_preference_proposal(arguments.get("preferences") or [])
        raise ValueError(f"Unknown tool: {name}")

    async def call(self, session_id: str, name: str, arguments: dict[str, Any], trace: list[dict[str, Any]]) -> Any:
        started = time.perf_counter()
        try:
            result = await self.execute(session_id, name, arguments)
            trace.append({
                "tool": name,
                "arguments": arguments,
                "success": True,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "summary": summarize_result(result),
            })
            return result
        except Exception as exc:
            trace.append({
                "tool": name,
                "arguments": arguments,
                "success": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc),
            })
            raise

    async def price_analysis(self, product_id: str, trace: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._legacy.call("PriceTool", {"product_id": product_id}, trace)


def compact_product(product: dict[str, Any]) -> dict[str, Any]:
    source = product.get("sourceFields") or {}
    return {
        "id": product.get("id"),
        "title": product.get("name"),
        "brand": product.get("brand"),
        "category": product.get("category"),
        "reference_price": reference_amount(product),
        "rating": product.get("rating"),
        "review_count": product.get("reviewCount"),
        "features": (source.get("features") or [])[:6],
        "details": dict(list((source.get("details") or {}).items())[:10]),
    }


def compare_products(product_ids: list[str], criteria: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(item for item in product_ids if item))[:4]
    if len(unique) < 2:
        raise ValueError("compare_products requires 2 to 4 product ids")
    products = [item for item in product_service.get_products(unique) if item]
    if len(products) < 2:
        raise ValueError("Products not found in catalog")
    winner_id, verdict = comparison_verdict(products)
    rows = []
    for product in products:
        price = reference_amount(product)
        rows.append({
            "product_id": product.get("id"),
            "title": product.get("name"),
            "reference_price": price,
            "rating": product.get("rating"),
            "review_count": product.get("reviewCount"),
            "snapshot": snapshot(product),
        })
    price_delta = None
    if len(products) == 2:
        left, right = reference_amount(products[0]), reference_amount(products[1])
        if left is not None and right is not None:
            price_delta = round(left - right, 2)
    return {
        "criteria": criteria,
        "winner_product_id": winner_id,
        "verdict": verdict,
        "rows": rows,
        "price_delta_first_vs_second": price_delta,
    }


def validate_cart_proposal(session_id: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
    validated = []
    for change in changes[:6]:
        action = change.get("action")
        product_id = change.get("product_id")
        if action not in {"add", "remove"} or not product_id:
            continue
        product = product_service.get_products([product_id])
        if not product and action == "add":
            continue
        validated.append({"action": action, "product_id": product_id})
    proposal_id = f"prop-{secrets.token_hex(6)}"
    return {
        "proposal_id": proposal_id,
        "status": "validated" if validated else "failed",
        "changes": validated,
        "requires_confirmation": True,
    }


def validate_preference_proposal(preferences: list[str]) -> dict[str, Any]:
    cleaned = [item.strip()[:100] for item in preferences if item and item.strip()]
    proposal_id = f"prop-{secrets.token_hex(6)}"
    return {
        "proposal_id": proposal_id,
        "status": "validated" if cleaned else "failed",
        "preferences": cleaned,
        "requires_confirmation": True,
    }


def summarize_result(value: Any) -> str:
    if isinstance(value, dict):
        if "products" in value:
            return f"{len(value['products'])} products"
        if "items" in value:
            return f"{len(value['items'])} items"
        if "changes" in value:
            return f"{len(value['changes'])} cart changes"
    if isinstance(value, list):
        return f"{len(value)} rows"
    return str(value)[:120]
