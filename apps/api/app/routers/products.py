from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..db import AUTHORIZED_CATEGORY, database_config
from ..services.products import catalog_summary, get_product, list_products, price_history, repository, schema_kind

router = APIRouter()


@router.get("/catalog")
def catalog() -> dict:
    summary = catalog_summary()
    return {
        **database_config(),
        "schema": schema_kind(),
        **summary,
    }


@router.get("/products")
def products(
    q: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    max_price: float | None = Query(default=None),
    sort: str = Query(default="recommended"),
    limit: int = Query(default=24, ge=1, le=48),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = list_products(q=q, brand=brand, max_price=max_price, sort=sort, limit=limit, offset=offset)
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "count": len(items),
        "category": AUTHORIZED_CATEGORY,
    }


@router.get("/products/{product_id}")
def product(product_id: str) -> dict:
    item = get_product(product_id)
    if not item:
        raise HTTPException(404, "Product not found in the Home Audio & Theater catalog")
    return item


@router.get("/products/{product_id}/price-history")
def product_price_history(product_id: str) -> list[dict]:
    return price_history(product_id)


@router.get("/products/{product_id}/evidence")
def product_evidence(product_id: str) -> dict:
    if not get_product(product_id):
        raise HTTPException(404, "Product not found in the Home Audio & Theater catalog")
    return repository.get_evidence(product_id)
