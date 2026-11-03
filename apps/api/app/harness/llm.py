from __future__ import annotations

import os
from typing import Any

import httpx


class LLMProvider:
    async def summarize(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    async def summarize(self, payload: dict[str, Any]) -> str:
        primary = payload.get("primary")
        if not primary:
            return "Picki did not find a product that matches the hard constraints."
        product = primary["product"]
        if product.get("sourceFields", {}).get("schema") in {"pickmate_subset", "ecomagentbench_product_db"}:
            return f"Picki checked price, rating, features, details, and reviews in product.db. Current first pick: {product['name']}."
        return f"Picki checked budget, compatibility, price history, reviews, and video evidence. Current first pick: {product['name']}."


class OpenAICompatibleProvider(LLMProvider):
    async def summarize(self, payload: dict[str, Any]) -> str:
        if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL"):
            return await MockLLMProvider().summarize(payload)
        prompt = {
            "model": os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            "messages": [
                {"role": "system", "content": "Explain the shopping recommendation in concise English. Do not change product ranking or add unsupported claims."},
                {"role": "user", "content": str(payload)[:6000]},
            ],
        }
        base = os.getenv("LLM_BASE_URL", "").rstrip("/")
        headers = {"authorization": f"Bearer {os.getenv('LLM_API_KEY')}", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(f"{base}/chat/completions", json=prompt, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    return OpenAICompatibleProvider() if os.getenv("LLM_MODE", "mock") == "real" else MockLLMProvider()
