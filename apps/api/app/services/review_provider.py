from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import products as product_service

PROVIDER_CATALOG = "catalog"
PROVIDER_HTTP = "http"


def search_config() -> dict[str, str | None]:
    return {
        "provider": (os.getenv("PICKI_SEARCH_PROVIDER") or PROVIDER_CATALOG).strip().lower(),
        "api_key": os.getenv("PICKI_SEARCH_API_KEY"),
        "api_base_url": (os.getenv("PICKI_SEARCH_API_BASE_URL") or "").rstrip("/"),
    }


def fetch_review_intelligence(product: dict[str, Any]) -> dict[str, Any]:
    product_id = str(product.get("id") or "")
    cfg = search_config()
    provider = cfg["provider"] or PROVIDER_CATALOG
    if provider in {PROVIDER_CATALOG, "", "none", "off"}:
        return _from_catalog(product_id, product, source="catalog")
    if provider == PROVIDER_HTTP and cfg.get("api_base_url"):
        remote = _from_http(product_id, str(cfg["api_base_url"]), cfg.get("api_key"))
        if remote.get("available"):
            return remote
    return _from_catalog(product_id, product, source="catalog_fallback")


def _from_catalog(product_id: str, product: dict[str, Any], source: str) -> dict[str, Any]:
    reviews = product_service.review_evidence(product_id) if product_id else []
    rating = product.get("rating")
    count = int(product.get("reviewCount") or 0)
    positives: list[str] = []
    complaints: list[str] = []
    sources: list[dict[str, Any]] = []
    for review in reviews[:8]:
        content = (review.get("content") or review.get("text") or "").strip()
        if not content:
            continue
        sources.append({
            "source": source,
            "rating": review.get("rating"),
            "verified": review.get("verified_purchase") or review.get("verified"),
            "snippet": content[:220],
        })
        lower = content.lower()
        if any(token in lower for token in ("defect", "broken", "fail", "return", "cheap", "issue", "problem")):
            complaints.append(content[:160])
        else:
            positives.append(content[:160])
    available = bool(reviews) or (rating and count > 0)
    if not available:
        return {
            "available": False,
            "provider": source,
            "summary": "Customer review text is unavailable in the catalog for this listing.",
            "positives": [],
            "complaints": [],
            "rating": rating,
            "review_count": count,
            "sources": [],
        }
    summary = f"Catalog shows {rating:.1f}/5 across {count} reviews." if rating and count else "Review excerpts available from the catalog."
    return {
        "available": True,
        "provider": source,
        "summary": summary,
        "positives": positives[:3],
        "complaints": complaints[:3],
        "rating": rating,
        "review_count": count,
        "sources": sources[:5],
    }


def _from_http(product_id: str, base_url: str, api_key: str | None) -> dict[str, Any]:
    url = f"{base_url}/reviews?product_id={urllib.parse.quote(product_id)}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {"available": False, "provider": "http", "summary": "External review provider unavailable.", "sources": []}
    if not isinstance(payload, dict):
        return {"available": False, "provider": "http", "summary": "External review provider returned invalid data.", "sources": []}
    reviews = payload.get("reviews") if isinstance(payload.get("reviews"), list) else []
    positives = [str(item.get("snippet") or item.get("content") or "")[:160] for item in reviews if item.get("sentiment") != "negative"][:3]
    complaints = [str(item.get("snippet") or item.get("content") or "")[:160] for item in reviews if item.get("sentiment") == "negative"][:3]
    rating = payload.get("rating")
    count = int(payload.get("review_count") or len(reviews) or 0)
    sources = []
    for item in reviews[:5]:
        snippet = str(item.get("snippet") or item.get("content") or "").strip()
        if snippet:
            sources.append({"source": item.get("source") or "external", "snippet": snippet[:220], "rating": item.get("rating")})
    summary = str(payload.get("summary") or "").strip()
    if not summary and count:
        summary = f"External provider reports {count} reviews."
    return {
        "available": bool(reviews or summary),
        "provider": "http",
        "summary": summary or "External review data retrieved.",
        "positives": positives,
        "complaints": complaints,
        "rating": rating,
        "review_count": count,
        "sources": sources,
    }
