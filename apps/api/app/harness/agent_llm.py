from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


def model_config() -> dict[str, Any]:
    api_key = os.getenv("PICKI_MODEL_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = (os.getenv("PICKI_MODEL_BASE_URL") or os.getenv("LLM_BASE_URL") or "").rstrip("/")
    model = os.getenv("PICKI_MODEL_NAME") or os.getenv("LLM_MODEL", "gpt-4.1-mini")
    max_rounds = int(os.getenv("PICKI_MAX_TOOL_ROUNDS", "3"))
    return {"api_key": api_key, "base_url": base_url, "model": model, "max_rounds": max(1, min(max_rounds, 3))}


def agent_mode() -> str:
    raw = (os.getenv("PICKI_AGENT_MODE") or os.getenv("PICKI_MODE") or "").lower()
    if raw in {"deterministic", "mock"}:
        return "deterministic"
    if raw == "assist":
        return "assist"
    if raw == "model":
        return "model"
    cfg = model_config()
    if cfg["api_key"] and cfg["base_url"] and os.getenv("LLM_MODE", "mock") == "real":
        return "assist"
    return "deterministic"


def llm_allowed() -> bool:
    if agent_mode() == "deterministic":
        return False
    from ..services.picki_llm import llm_configured
    return bool(llm_configured())


class AgentModelClient:
    async def plan_tool_calls(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        context: dict[str, Any],
        prior_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if agent_mode() == "model" and llm_allowed():
            return await self._model_plan(messages, tools)
        return deterministic_plan(context, prior_results)

    async def finalize_structured(
        self,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if agent_mode() == "model" and llm_allowed():
            return await self._model_finalize(context, tool_results)
        return deterministic_structured(context, tool_results)

    async def _model_plan(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        cfg = model_config()
        payload = {"model": cfg["model"], "messages": messages, "tools": tools, "tool_choice": "auto"}
        headers = {"authorization": f"Bearer {cfg['api_key']}", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{cfg['base_url']}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        message = data["choices"][0]["message"]
        calls = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": fn.get("name"), "arguments": args})
        return {"tool_calls": calls, "raw": data}

    async def _model_finalize(self, context: dict[str, Any], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
        cfg = model_config()
        prompt = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with keys: message, direct_recommendation, product_highlights, "
                        "technical_specifications, price_value_analysis, customer_review_summary, product_comparisons, "
                        "important_drawbacks, suggested_follow_up_questions, proposed_actions. "
                        "Use catalog facts from tool results only."
                    ),
                },
                {"role": "user", "content": json.dumps({"context": context, "tool_results": tool_results})[:12000]},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"authorization": f"Bearer {cfg['api_key']}", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(f"{cfg['base_url']}/chat/completions", json=prompt, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"message": content}


def deterministic_plan(context: dict[str, Any], prior_results: list[dict[str, Any]]) -> dict[str, Any]:
    message = (context.get("user_message") or "").lower()
    focus = context.get("focus_product_ids") or []
    executed = {item.get("tool") for item in prior_results}
    calls: list[dict[str, Any]] = []
    if "get_cart" not in executed and ("cart" in message or "my picks" in message):
        calls.append({"name": "get_cart", "arguments": {}})
    if focus and "get_product_details" not in executed:
        calls.append({"name": "get_product_details", "arguments": {"product_ids": focus[:3]}})
    from ..services.product_relevance import search_query_for_intent

    intent = context.get("product_intent")
    cheaper_intent = any(token in message for token in ("cheaper", "overpay", "less expensive", "affordable"))
    if cheaper_intent and "search_products" not in executed:
        query = search_query_for_intent(intent, context.get("user_message") or "") if intent else (context.get("user_message") or "hdmi cable")
        calls.append({"name": "search_products", "arguments": {"query": query, "filters": {}}})
    if focus and any(token in message for token in ("review", "customer", "feedback")) and "get_product_reviews" not in executed:
        calls.append({"name": "get_product_reviews", "arguments": {"product_ids": focus[:2]}})
    if "get_user_preferences" not in executed and any(token in message for token in ("taste", "preference", "usually", "remember")):
        calls.append({"name": "get_user_preferences", "arguments": {}})
    if "compare" in message and len(focus) >= 2 and "compare_products" not in executed:
        calls.append({"name": "compare_products", "arguments": {"product_ids": focus[:4], "criteria": ["price", "rating"]}})
    if "search_products" not in executed and not focus and len(message) > 4:
        query = search_query_for_intent(intent, context.get("user_message") or "") if intent else context.get("user_message")
        calls.append({"name": "search_products", "arguments": {"query": query, "filters": {}}})
    if not calls and focus and "get_product_reviews" not in executed:
        calls.append({"name": "get_product_reviews", "arguments": {"product_ids": focus[:1]}})
    if not calls and not focus:
        calls.append({"name": "search_products", "arguments": {"query": context.get("user_message") or "home audio", "filters": {}}})
    return {"tool_calls": calls[:2]}


def deterministic_structured(context: dict[str, Any], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    message = context.get("user_message") or ""
    products = []
    comparison = None
    reviews_available = False
    for block in tool_results:
        if block.get("tool") == "search_products":
            products = (block.get("result") or {}).get("products") or []
        if block.get("tool") == "get_product_details":
            products = (block.get("result") or {}).get("products") or products
        if block.get("tool") == "compare_products":
            comparison = block.get("result")
        if block.get("tool") == "get_product_reviews":
            for item in (block.get("result") or {}).get("items") or []:
                if item.get("available"):
                    reviews_available = True
    primary = products[0] if products else None
    concise = len(message.split()) <= 8 and not comparison
    highlights = []
    specs = []
    drawbacks = []
    if primary:
        highlights.extend([str(item) for item in (primary.get("features") or [])[:3]])
        specs.extend([f"{key}: {value}" for key, value in (primary.get("details") or {}).items()][:4])
        if primary.get("reference_price") is None:
            drawbacks.append("Catalog reference price is unavailable.")
    review_summary = None
    if reviews_available:
        review_summary = "Review excerpts are available from the catalog for this product."
    else:
        review_summary = "Customer review text is unavailable or limited in the catalog."
    price_line = None
    if primary and primary.get("reference_price") is not None:
        price_line = f"Catalog reference price is ${float(primary['reference_price']):.2f}."
    elif comparison and comparison.get("price_delta_first_vs_second") is not None:
        delta = comparison["price_delta_first_vs_second"]
        price_line = f"Reference price difference between the first two items is ${abs(delta):.2f} ({'lower' if delta < 0 else 'higher'} for the first item)."
    direct = None
    if primary:
        direct = f"My current pick from verified catalog data is {primary.get('title')}."
    if comparison:
        direct = comparison.get("verdict")
    body = direct or (f"Here is what I found in the catalog for: {message}" if message else "Tell me what you are shopping for.")
    if concise:
        return {
            "message": body,
            "direct_recommendation": direct,
            "customer_review_summary": review_summary if "review" in message.lower() else None,
            "price_value_analysis": price_line,
            "product_highlights": highlights[:2],
            "technical_specifications": [],
            "important_drawbacks": drawbacks[:1],
            "suggested_follow_up_questions": [],
            "proposed_actions": [],
        }
    return {
        "message": body,
        "direct_recommendation": direct,
        "product_highlights": highlights,
        "technical_specifications": specs,
        "price_value_analysis": price_line,
        "customer_review_summary": review_summary,
        "product_comparisons": comparison.get("verdict") if comparison else None,
        "important_drawbacks": drawbacks,
        "suggested_follow_up_questions": ["Want a cheaper option?", "Should I compare two picks?", "Add this to your cart?"],
        "proposed_actions": [],
    }


def parse_fallback_tool_calls(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    calls = payload.get("tool_calls")
    if not isinstance(calls, list):
        return []
    out = []
    for call in calls:
        if isinstance(call, dict) and call.get("name"):
            out.append({"name": call["name"], "arguments": call.get("arguments") or {}})
    return out
