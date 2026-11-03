from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..db import AUTHORIZED_CATEGORY, decode_json, product_one
from ..services.catalog_art import catalog_image_png
from ..services.products import collect_image_urls

router = APIRouter()

ALLOWED_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "images.amazon.com",
    "ecx.images-amazon.com",
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.amazon.com/",
}


@router.get("/media/product/{product_id}")
async def product_media(product_id: str) -> Response:
    for url in product_image_candidates(product_id):
        try:
            return await fetch_remote_image(url)
        except HTTPException:
            continue
    return Response(
        content=catalog_image_png(product_id),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def product_image_candidates(product_id: str) -> list[str]:
    row = product_one(
        "SELECT * FROM products WHERE product_id=? AND main_category=?",
        (product_id, AUTHORIZED_CATEGORY),
    )
    if not row:
        return []
    data = decode_json(row.get("data"), {})
    return collect_image_urls(data.get("images"), data.get("image"), data.get("hi_res"))


@router.get("/media/catalog/{token}")
def catalog_media(token: str) -> Response:
    return Response(
        content=catalog_image_png(token),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/media")
async def proxy_media(url: str = Query(..., min_length=8, max_length=2000)) -> Response:
    return await fetch_remote_image(url)


async def fetch_remote_image(url: str) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Invalid image url")
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS and not host.endswith(".media-amazon.com") and not host.endswith(".ssl-images-amazon.com"):
        raise HTTPException(400, "Unsupported image host")
    candidates = [url]
    if "._AC_SL800_." in url:
        candidates.append(url.replace("._AC_SL800_.", "._AC_."))
        candidates.append(url.replace("._AC_SL800_.", "."))
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            remote = None
            for candidate in candidates:
                try:
                    remote = await client.get(candidate, headers=BROWSER_HEADERS)
                except httpx.HTTPError:
                    continue
                if remote.status_code < 400 and remote.content:
                    break
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Image fetch failed: {exc}") from exc
    if remote is None or remote.status_code >= 400 or not remote.content:
        raise HTTPException(404, "Image not found")
    content_type = remote.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if not content_type.startswith("image/"):
        content_type = "image/jpeg"
    return Response(
        content=remote.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
