from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import math
import re
from typing import Any

from ..db import AUTHORIZED_CATEGORY, PRODUCT_DB_PATH, decode_json, one, product_one, product_query, query

ECOM_SCHEMA = "ecomagentbench_product_db"
PICKMATE_SUBSET_SCHEMA = "pickmate_subset"
PICKMATE_SCHEMA = "pickmate_mvp"
HOME_AUDIO = AUTHORIZED_CATEGORY
AMAZON_IMAGE_SUFFIX = re.compile(r"\._[A-Za-z0-9,_]+_\.(jpg|jpeg|png|webp)$", re.I)


def upgrade_image_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if AMAZON_IMAGE_SUFFIX.search(value):
        return AMAZON_IMAGE_SUFFIX.sub(r"._AC_SL800_.\1", value)
    return value


def collect_image_urls(*sources: Any) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str):
            for part in [value, *re.findall(r"https?://[^\s\"']+", value)]:
                upgraded = upgrade_image_url(part)
                if upgraded.startswith("http") and upgraded not in seen:
                    seen.add(upgraded)
                    found.append(upgraded)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in {"image", "images", "imageurl", "image_url", "hires", "thumb", "thumbnail"}:
                    walk(item)
                elif isinstance(item, (list, dict, str)) and "image" in str(key).lower():
                    walk(item)

    for source in sources:
        walk(source)
    return found


class ProductRepository(ABC):
    @abstractmethod
    def search_products(self, text: str | None = None, category: str | None = None, max_price: float | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_products(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_product(self, product_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def get_products_by_ids(self, product_ids: list[str] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_reviews(self, product_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_evidence(self, product_id: str) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError


class EComAgentBenchProductRepository(ProductRepository):
    def search_products(self, text: str | None = None, category: str | None = None, max_price: float | None = None) -> list[dict[str, Any]]:
        return search_ecom_products(text, category, max_price)

    def list_products(self) -> list[dict[str, Any]]:
        return list_home_audio_products(limit=24, offset=0, include_evidence=False)

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        row = product_one(
            "SELECT * FROM products WHERE product_id=? AND main_category=?",
            (product_id, HOME_AUDIO),
        )
        return ecom_product_payload(row, include_evidence=True) if row else None

    def get_products_by_ids(self, product_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if not product_ids:
            return search_ecom_products("home audio", None)
        found = {
            row["product_id"]: ecom_product_payload(row, include_evidence=True)
            for row in product_query(
                f"SELECT * FROM products WHERE main_category=? AND product_id IN ({','.join('?' for _ in product_ids)})",
                (HOME_AUDIO, *product_ids),
            )
        }
        return [found[pid] for pid in product_ids if pid in found]

    def get_reviews(self, product_id: str) -> list[dict[str, Any]]:
        return [
            ecom_review_payload(row)
            for row in product_query(
                "SELECT * FROM reviews WHERE product_id=? ORDER BY verified_purchase DESC, helpful_vote DESC, rating DESC LIMIT 20",
                (product_id,),
            )
        ] if table_exists("reviews") else []

    def get_evidence(self, product_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "reviews": self.get_reviews(product_id),
            "discussions": [],
            "questions": [],
            "videos": [],
            "price_history": price_history(product_id),
        }


class SQLiteProductRepository(ProductRepository):
    def search_products(self, text: str | None = None, category: str | None = None, max_price: float | None = None) -> list[dict[str, Any]]:
        require_authorized_catalog()
        return EComAgentBenchProductRepository().search_products(text, category, max_price)

    def list_products(self) -> list[dict[str, Any]]:
        return list_products()

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        return get_product(product_id)

    def get_products_by_ids(self, product_ids: list[str] | None = None) -> list[dict[str, Any]]:
        return get_products(product_ids)

    def get_reviews(self, product_id: str) -> list[dict[str, Any]]:
        return review_evidence(product_id)

    def get_evidence(self, product_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "reviews": review_evidence(product_id),
            "discussions": discussion_evidence(product_id),
            "questions": question_evidence(product_id),
            "videos": video_evidence(product_id),
            "price_history": price_history(product_id),
        }


repository: ProductRepository = SQLiteProductRepository()


def require_authorized_catalog() -> None:
    if schema_kind() != ECOM_SCHEMA:
        raise RuntimeError("PickMate product queries require the Amazon Home Audio & Theater product.db")


def list_products(
    *,
    q: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    sort: str = "recommended",
    limit: int = 24,
    offset: int = 0,
    include_evidence: bool = False,
) -> list[dict[str, Any]]:
    require_authorized_catalog()
    return list_home_audio_products(
        q=q,
        brand=brand,
        max_price=max_price,
        sort=sort,
        limit=limit,
        offset=offset,
        include_evidence=include_evidence,
    )


def catalog_summary() -> dict[str, Any]:
    require_authorized_catalog()
    count_row = product_one("SELECT COUNT(*) AS n FROM products WHERE main_category=?", (HOME_AUDIO,))
    priced = product_one(
        "SELECT COUNT(*) AS n FROM products WHERE main_category=? AND has_price=1",
        (HOME_AUDIO,),
    )
    brands = [
        row["brand"]
        for row in product_query(
            "SELECT brand, COUNT(*) AS n FROM products "
            "WHERE main_category=? AND brand IS NOT NULL AND TRIM(brand) != '' "
            "GROUP BY brand ORDER BY n DESC LIMIT 40",
            (HOME_AUDIO,),
        )
    ]
    return {
        "product_count": int(count_row["n"] if count_row else 0),
        "priced_count": int(priced["n"] if priced else 0),
        "currency": "USD",
        "categories": [HOME_AUDIO],
        "brands": brands,
        "product_types": ["Soundbar", "Speaker", "Receiver", "Amplifier", "Home Theater", "Cable"],
    }


def list_home_audio_products(
    *,
    q: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    sort: str = "recommended",
    limit: int = 24,
    offset: int = 0,
    include_evidence: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["main_category=?"]
    params: list[Any] = [HOME_AUDIO]
    if brand and brand.lower() not in {"all", "any"}:
        clauses.append("LOWER(brand)=?")
        params.append(brand.lower())
    if max_price is not None:
        clauses.append("has_price=1 AND price IS NOT NULL AND price <= ?")
        params.append(max_price)
    tokens = search_tokens(q or "")[:8]
    if tokens:
        like = " OR ".join(["LOWER(title || ' ' || COALESCE(store,'') || ' ' || COALESCE(brand,'')) LIKE ?" for _ in tokens])
        clauses.append(f"({like})")
        params.extend(f"%{token.lower()}%" for token in tokens)
    order = {
        "price_low": "has_price DESC, price ASC, rating_number DESC",
        "price_high": "has_price DESC, price DESC, rating_number DESC",
        "rating": "average_rating DESC, rating_number DESC",
        "reviews": "rating_number DESC, average_rating DESC",
    }.get(sort, "has_price DESC, rating_number DESC, average_rating DESC")
    limit = max(1, min(int(limit), 48))
    offset = max(0, int(offset))
    rows = product_query(
        f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return [ecom_product_payload(row, include_evidence=include_evidence) for row in rows]


def get_product(product_id: str) -> dict[str, Any] | None:
    require_authorized_catalog()
    return EComAgentBenchProductRepository().get_product(product_id)


def get_products(product_ids: list[str] | None = None) -> list[dict[str, Any]]:
    require_authorized_catalog()
    return EComAgentBenchProductRepository().get_products_by_ids(product_ids)


def price_history(product_id: str) -> list[dict[str, Any]]:
    if schema_kind() == ECOM_SCHEMA:
        row = product_one(
            "SELECT price FROM products WHERE product_id=? AND main_category=?",
            (product_id, HOME_AUDIO),
        )
        if not row or row.get("price") is None:
            return []
        return [{
            "id": f"{product_id}-current-price",
            "productId": product_id,
            "date": "2026-08-06",
            "price": row["price"],
            "promotionType": "current_price",
            "source": "product.db price",
            "verifiedAt": "2026-08-06T00:00:00+00:00",
        }]
    if schema_kind() == PICKMATE_SUBSET_SCHEMA:
        row = one("SELECT price FROM products WHERE id=?", (product_id,))
        if not row or row.get("price") is None:
            return []
        return [{
            "id": f"{product_id}-current-price",
            "productId": product_id,
            "date": "2026-08-06",
            "price": row["price"],
            "promotionType": "current_price",
            "source": "pickmate subset price",
            "verifiedAt": "2026-08-06T00:00:00+00:00",
        }]
    return [price_payload(row) for row in query("SELECT * FROM price_history WHERE product_id=? ORDER BY date ASC", (product_id,))]


def review_evidence(product_id: str) -> list[dict[str, Any]]:
    if schema_kind() == ECOM_SCHEMA:
        if not table_exists("reviews"):
            return []
        return [
            ecom_review_payload(row)
            for row in product_query(
                "SELECT * FROM reviews WHERE product_id=? ORDER BY verified_purchase DESC, helpful_vote DESC, rating DESC LIMIT 20",
                (product_id,),
            )
        ]
    if schema_kind() == PICKMATE_SUBSET_SCHEMA:
        return [
            subset_review_payload(row)
            for row in query(
                "SELECT * FROM reviews WHERE product_id=? ORDER BY verified_purchase DESC, helpful_vote DESC, rating DESC LIMIT 20",
                (product_id,),
            )
        ]
    return [review_payload(row) for row in query("SELECT * FROM review_evidence WHERE product_id=? ORDER BY helpful_count DESC", (product_id,))]


def discussion_evidence(product_id: str) -> list[dict[str, Any]]:
    if schema_kind() in {ECOM_SCHEMA, PICKMATE_SUBSET_SCHEMA}:
        return []
    return [discussion_payload(row) for row in query("SELECT * FROM discussion_evidence WHERE product_id=?", (product_id,))]


def question_evidence(product_id: str) -> list[dict[str, Any]]:
    if schema_kind() in {ECOM_SCHEMA, PICKMATE_SUBSET_SCHEMA}:
        return []
    return [question_payload(row) for row in query("SELECT * FROM product_questions WHERE product_id=?", (product_id,))]


def video_evidence(product_id: str) -> list[dict[str, Any]]:
    if schema_kind() in {ECOM_SCHEMA, PICKMATE_SUBSET_SCHEMA}:
        return []
    return [video_payload(row) for row in query("SELECT * FROM video_evidence WHERE product_id=?", (product_id,))]


def schema_kind() -> str:
    columns = table_columns("products")
    if "product_id" in columns and "data" in columns:
        return ECOM_SCHEMA
    return "unauthorized"


def table_exists(name: str) -> bool:
    return bool(product_one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))


def table_columns(name: str) -> set[str]:
    if not PRODUCT_DB_PATH.exists():
        return set()
    try:
        rows = product_query(f"PRAGMA table_info({name})")
    except Exception:
        return set()
    return {row["name"] for row in rows}


def search_ecom_products(text: str | None, category: str | None = None, max_price: float | None = None) -> list[dict[str, Any]]:
    clauses = ["main_category=?"]
    params: list[Any] = [HOME_AUDIO]
    if max_price is not None:
        clauses.append("has_price=1 AND price IS NOT NULL AND price <= ?")
        params.append(max_price)
    type_tokens = search_tokens(category or "") if category and category.lower() not in {"any", HOME_AUDIO.lower(), "home audio & theater"} else []
    if text and table_exists("products_fts"):
        tokens = search_tokens(text)
        if tokens:
            fts_query = " OR ".join(f'"{token}"' for token in tokens[:10])
            try:
                rows = product_query(
                    "SELECT p.* FROM products_fts "
                    "JOIN products p ON p.rowid = products_fts.rowid "
                    "WHERE products_fts MATCH ? AND p.main_category=? AND p.has_price=1 "
                    + ("AND p.price <= ? " if max_price is not None else "")
                    + "ORDER BY bm25(products_fts) LIMIT 80",
                    (fts_query, HOME_AUDIO, *([max_price] if max_price is not None else [])),
                )
                filtered = rows
                if type_tokens:
                    filtered = [
                        row for row in rows
                        if any(token in str(row.get("title") or "").lower() for token in type_tokens)
                    ] or rows
                if filtered:
                    return [ecom_product_payload(row, include_evidence=True) for row in filtered]
            except Exception:
                pass
    if text:
        tokens = search_tokens(text)[:8]
        if tokens:
            like_clause = " OR ".join(["LOWER(title || ' ' || COALESCE(store,'') || ' ' || COALESCE(brand,'')) LIKE ?" for _ in tokens])
            rows = product_query(
                f"SELECT * FROM products WHERE {' AND '.join(clauses)} AND has_price=1 AND ({like_clause}) "
                "ORDER BY rating_number DESC, average_rating DESC LIMIT 80",
                (*params, *(f"%{token.lower()}%" for token in tokens)),
            )
            if rows:
                return [ecom_product_payload(row, include_evidence=True) for row in rows]
    if type_tokens:
        like_clause = " OR ".join(["LOWER(title) LIKE ?" for _ in type_tokens])
        rows = product_query(
            f"SELECT * FROM products WHERE {' AND '.join(clauses)} AND has_price=1 AND ({like_clause}) "
            "ORDER BY rating_number DESC, average_rating DESC LIMIT 80",
            (*params, *(f"%{token}%" for token in type_tokens)),
        )
        if rows:
            return [ecom_product_payload(row, include_evidence=True) for row in rows]
    return [
        ecom_product_payload(row, include_evidence=True)
        for row in product_query(
            f"SELECT * FROM products WHERE {' AND '.join(clauses)} AND has_price=1 "
            "ORDER BY rating_number DESC, average_rating DESC LIMIT 80",
            tuple(params),
        )
    ]


def search_pickmate_subset_products(text: str | None, category: str | None = None) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if category and category != "any":
        clauses.append("LOWER(category) LIKE ?")
        params.append(f"%{category.lower()}%")
    tokens = search_tokens(text or "")[:8]
    if tokens:
        search_cols = (
            "LOWER(title || ' ' || brand || ' ' || category || ' ' || "
            "features || ' ' || description || ' ' || raw_attributes)"
        )
        clauses.append("(" + " OR ".join([f"{search_cols} LIKE ?" for _ in tokens]) + ")")
        params.extend(f"%{token.lower()}%" for token in tokens)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = query(
        f"SELECT * FROM products {where} ORDER BY rating_count DESC, rating DESC LIMIT 120",
        tuple(params),
    )
    return [subset_product_payload(row, include_evidence=True) for row in rows]


def subset_product_payload(row: dict[str, Any], include_evidence: bool = True) -> dict[str, Any]:
    raw = decode_json(row.get("raw_attributes"), {})
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    details = raw.get("details") or data.get("details") or {}
    features = normalize_text_list(decode_json(row.get("features"), []))
    description = normalize_text_list(decode_json(row.get("description"), []))
    product_id = row["id"]
    title = row.get("title") or data.get("title") or product_id
    brand = row.get("brand") or details.get("Brand") or data.get("brand") or data.get("store") or ""
    price = row.get("price")
    rating = row.get("rating") or data.get("average_rating") or 0
    rating_count = row.get("rating_count") or data.get("rating_number") or 0
    reviews = review_evidence(product_id) if include_evidence else []
    attrs = unknown_product_attributes()
    positive, negative = review_themes(reviews, features)
    summary = description[0] if description else features[0] if features else title
    image_urls = collect_image_urls(row.get("image"), data.get("images"), data.get("image"), data.get("hi_res"), raw.get("images"))
    product = {
        "id": product_id,
        "brand": str(brand),
        "name": title,
        "slug": product_id,
        "category": row.get("category") or data.get("main_category") or "general_product",
        "description": summary,
        "currentPrice": price if price is not None else 0,
        "originalPrice": price if price is not None else 0,
        "currency": "USD",
        "stockStatus": "unknown",
        "sellerType": raw.get("store") or data.get("store") or "",
        "deliveryText": "",
        "returnPolicy": "",
        "warrantyText": "",
        "rating": float(rating or 0),
        "reviewCount": int(rating_count or 0),
        "imageUrls": image_urls,
        "lastUpdatedAt": row.get("data_updated_at") or "2026-08-06T00:00:00+00:00",
        "dataUpdatedAt": row.get("data_updated_at") or "2026-08-06T00:00:00+00:00",
        "attributes": attrs,
        "priceHistory": price_history(product_id) if include_evidence else [],
        "reviews": reviews,
        "discussions": [],
        "questions": [],
        "videos": [],
        "positiveThemes": positive,
        "negativeThemes": negative,
        "bestFor": [row.get("category") or data.get("main_category") or ""] if (row.get("category") or data.get("main_category")) else [],
        "notFor": [],
        "sourceFields": {
            "schema": PICKMATE_SUBSET_SCHEMA,
            "productId": product_id,
            "title": title,
            "mainCategory": row.get("category") or data.get("main_category") or "",
            "store": raw.get("store") or data.get("store") or "",
            "brand": str(brand),
            "price": price,
            "averageRating": float(rating or 0) if rating else None,
            "ratingNumber": int(rating_count or 0),
            "features": features,
            "description": description,
            "details": details,
            "rawAttributes": raw,
        },
    }
    product["standardizedDimensions"] = product_db_dimensions(product)
    return product


def subset_review_payload(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("title") or ""
    text = row.get("text") or ""
    content = ". ".join(part for part in [title, text] if part)
    rating = row.get("rating") or 0
    return {
        "id": str(row.get("id") or f"{row['product_id']}-review"),
        "productId": row["product_id"],
        "sourceType": "platform",
        "sourceName": "pickmate subset reviews",
        "content": content,
        "rating": rating,
        "verifiedPurchase": bool(row.get("verified_purchase")),
        "usageDuration": "",
        "userProfile": "Catalog reviewer",
        "topics": review_topics(content),
        "sentiment": review_sentiment(rating, content),
        "helpfulCount": int(row.get("helpful_vote") or 0),
        "createdAt": timestamp_to_iso(row.get("timestamp")),
    }


def subset_evidence(product_id: str) -> list[dict[str, Any]]:
    if not table_exists("evidence"):
        return []
    return [
        {
            "id": row["evidence_id"],
            "productId": row["product_id"],
            "sourceType": row["source_type"],
            "content": row["source_text"],
            "attribute": row["attribute"],
            "sentiment": row["sentiment"],
            "confidence": row["confidence"],
        }
        for row in query(
            "SELECT * FROM evidence WHERE product_id=? ORDER BY confidence DESC LIMIT 40",
            (product_id,),
        )
    ]


def ecom_product_payload(row: dict[str, Any], include_evidence: bool = True) -> dict[str, Any]:
    data = decode_json(row.get("data"), {})
    product_id = row["product_id"]
    details = data.get("details") or {}
    features = normalize_text_list(data.get("features"))
    description = normalize_text_list(data.get("description"))
    brand = row.get("brand") or details.get("Brand") or row.get("store") or ""
    title = row.get("title") or data.get("title") or product_id
    price = row.get("price")
    rating = row.get("average_rating") or data.get("average_rating") or 0
    rating_number = row.get("rating_number") or data.get("rating_number") or 0
    reviews = review_evidence(product_id) if include_evidence else []
    attrs = unknown_product_attributes()
    positive, negative = review_themes(reviews, features)
    summary = description[0] if description else features[0] if features else title
    product = {
        "id": product_id,
        "brand": str(brand),
        "name": title,
        "slug": product_id,
        "category": row.get("main_category") or data.get("main_category") or "general_product",
        "description": summary,
        "currentPrice": price if price is not None else 0,
        "originalPrice": price if price is not None else 0,
        "currency": "USD",
        "stockStatus": "unknown",
        "sellerType": row.get("store") or data.get("store") or "",
        "deliveryText": "",
        "returnPolicy": "",
        "warrantyText": "",
        "rating": float(rating or 0),
        "reviewCount": int(rating_number or 0),
        "imageUrls": normalize_text_list(data.get("images") or data.get("image") or []),
        "lastUpdatedAt": "2026-08-06T00:00:00+00:00",
        "dataUpdatedAt": "2026-08-06T00:00:00+00:00",
        "attributes": attrs,
        "priceHistory": ecom_price_history_from_row(row) if include_evidence else [],
        "reviews": reviews,
        "discussions": [],
        "questions": [],
        "videos": [],
        "positiveThemes": positive,
        "negativeThemes": negative,
        "bestFor": [row.get("main_category") or data.get("main_category") or ""] if (row.get("main_category") or data.get("main_category")) else [],
        "notFor": [],
        "sourceFields": {
            "schema": ECOM_SCHEMA,
            "productId": product_id,
            "title": title,
            "mainCategory": row.get("main_category") or data.get("main_category") or "",
            "store": row.get("store") or data.get("store") or "",
            "brand": str(brand),
            "price": price,
            "averageRating": float(rating or 0) if rating else None,
            "ratingNumber": int(rating_number or 0),
            "features": features,
            "description": description,
            "details": details,
        },
    }
    product["standardizedDimensions"] = product_db_dimensions(product)
    return product


def ecom_price_history_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    if row.get("price") is None:
        return []
    return [{
        "id": f"{row['product_id']}-current-price",
        "productId": row["product_id"],
        "date": "2026-08-06",
        "price": row["price"],
        "promotionType": "current_price",
        "source": "product.db price",
        "verifiedAt": "2026-08-06T00:00:00+00:00",
    }]


def ecom_review_payload(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("title") or ""
    text = row.get("text") or ""
    content = ". ".join(part for part in [title, text] if part)
    rating = row.get("rating") or 0
    return {
        "id": str(row.get("review_id") or f"{row['product_id']}-review"),
        "productId": row["product_id"],
        "sourceType": "platform",
        "sourceName": "product.db reviews",
        "content": content,
        "rating": rating,
        "verifiedPurchase": bool(row.get("verified_purchase")),
        "usageDuration": "",
        "userProfile": "Catalog reviewer",
        "topics": review_topics(content),
        "sentiment": review_sentiment(rating, content),
        "helpfulCount": int(row.get("helpful_vote") or 0),
        "createdAt": timestamp_to_iso(row.get("timestamp")),
    }


def normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def unknown_product_attributes() -> dict[str, Any]:
    return {
        "fitType": "general",
        "inEarDepth": "medium",
        "noiseCancellationScore": 50,
        "noiseCancellationDepth": 0,
        "comfortScore": 50,
        "smallEarFriendly": False,
        "singleEarWeight": 0,
        "earTipSizes": [],
        "callScore": 50,
        "windNoiseScore": 50,
        "batteryHours": 0,
        "totalBatteryHours": 0,
        "androidCompatible": True,
        "iosCompatible": True,
        "supportedCodecs": [],
        "multipoint": False,
        "waterResistance": "",
        "wirelessCharging": False,
        "transparencyMode": False,
        "appSupport": [],
        "microphoneCount": 0,
    }


def derived_attributes(
    title: str,
    features: list[str],
    description: list[str],
    details: dict[str, Any],
    reviews: list[dict[str, Any]],
    rating: float | int | None,
    rating_number: int | None,
) -> dict[str, Any]:
    text = text_blob(title, features, description, details, reviews)
    quality = rating_score(float(rating or 0), int(rating_number or 0))
    comfort = keyword_score(text, ["comfort", "comfortable", "fit", "ergonomic", "soft", "舒适", "舒服", "佩戴"], default=quality)
    noise = keyword_score(text, ["noise cancel", "noise-cancel", "anc", "quiet", "降噪", "安静"], default=quality - 8)
    call = keyword_score(text, ["call", "microphone", "voice", "meeting", "通话", "麦克风", "会议"], default=quality - 6)
    battery = keyword_score(text, ["battery", "hours", "charging", "charge", "电池", "续航"], default=quality - 4)
    compatibility = keyword_score(text, ["compatible", "connector", "model", "android", "ios", "bluetooth", "兼容", "适配"], default=quality - 3)
    water = "IPX5" if re.search(r"waterproof|water resistant|sweat|防水|出汗|ipx|ip\d", text, re.I) else ""
    return {
        "fitType": "in_ear" if re.search(r"earbud|headphone|耳机|耳塞", text, re.I) else "in_ear",
        "inEarDepth": "medium",
        "noiseCancellationScore": round(clamp(noise, 35, 98)),
        "noiseCancellationDepth": round(clamp(noise / 2, 15, 50)),
        "comfortScore": round(clamp(comfort, 35, 98)),
        "smallEarFriendly": bool(re.search(r"small ear|小耳|xs|extra small", text, re.I)),
        "singleEarWeight": 5.0,
        "earTipSizes": ["S", "M", "L"],
        "callScore": round(clamp(call, 35, 98)),
        "windNoiseScore": round(clamp(call - 8, 30, 90)),
        "batteryHours": round(clamp(battery / 10, 3, 12), 1),
        "totalBatteryHours": round(clamp(battery / 10 * 4, 12, 60), 1),
        "androidCompatible": not bool(re.search(r"iphone only|ios only|苹果专用", text, re.I)),
        "iosCompatible": not bool(re.search(r"android only|安卓专用", text, re.I)),
        "supportedCodecs": inferred_codecs(text),
        "multipoint": bool(re.search(r"multipoint|multi-point|multi device|多设备", text, re.I)),
        "waterResistance": water,
        "wirelessCharging": bool(re.search(r"wireless charging|无线充", text, re.I)),
        "transparencyMode": bool(re.search(r"transparency|ambient|通透", text, re.I)),
        "appSupport": [],
        "microphoneCount": 4 if re.search(r"microphone|mic|麦克风", text, re.I) else 0,
    }


def standardized_dimensions(product: dict[str, Any]) -> dict[str, Any]:
    attrs = product["attributes"]
    quality = rating_score(product.get("rating") or 0, product.get("reviewCount") or 0)
    durability = keyword_dimension(product, ["durable", "durability", "sturdy", "long lasting", "耐用", "耐久", "结实"], quality)
    return {
        "comfort": dimension_payload("comfort", "Comfort", attrs["comfortScore"], product, ["comfort", "comfortable", "fit", "舒适", "佩戴"]),
        "noise_cancellation": dimension_payload("noise_cancellation", "Noise cancellation", attrs["noiseCancellationScore"], product, ["noise cancel", "anc", "降噪"]),
        "compatibility": dimension_payload("compatibility", "Compatibility", 95 if attrs["androidCompatible"] and attrs["iosCompatible"] else 70, product, ["compatible", "android", "ios", "兼容"]),
        "durability": dimension_payload("durability", "Durability", durability, product, ["durable", "sturdy", "耐用"]),
        "quality": dimension_payload("quality", "Quality", quality, product, ["quality", "well made", "质量", "品质"]),
        "review_confidence": {
            "key": "review_confidence",
            "label": "Review confidence",
            "score": review_confidence_score(product),
            "polarity": "positive" if product.get("reviews") else "unknown",
            "sources": ["rating", "review"] if product.get("reviews") else ["rating"],
            "evidence": [f"{product.get('rating', 0):.1f}/5 from {product.get('reviewCount', 0)} reviews"],
        },
    }


def product_db_dimensions(product: dict[str, Any]) -> dict[str, Any]:
    quality = rating_score(product.get("rating") or 0, product.get("reviewCount") or 0)
    durability = keyword_dimension(product, ["durable", "durability", "sturdy", "long lasting", "耐用", "耐久", "结实"], quality)
    return {
        "quality": dimension_payload("quality", "Quality", quality, product, ["quality", "well made", "质量", "品质"]),
        "durability": dimension_payload("durability", "Durability", durability, product, ["durable", "sturdy", "耐用"]),
        "review_confidence": {
            "key": "review_confidence",
            "label": "Review confidence",
            "score": review_confidence_score(product),
            "polarity": "positive" if product.get("reviews") else "unknown",
            "sources": ["rating", "review"] if product.get("reviews") else ["rating"],
            "evidence": [f"{product.get('rating', 0):.1f}/5 from {product.get('reviewCount', 0)} reviews"],
        },
    }


def dimension_payload(key: str, label: str, score: float, product: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    evidence = []
    source = product.get("sourceFields", {})
    source_values = [
        *(source.get("features") or []),
        *(source.get("description") or []),
        *[f"{k}: {v}" for k, v in (source.get("details") or {}).items()],
    ]
    for value in source_values:
        if contains_any(str(value), keywords):
            evidence.append(str(value)[:120])
            break
    for review in product.get("reviews", []):
        if contains_any(review.get("content", ""), keywords):
            evidence.append(review["content"][:120])
            break
    return {
        "key": key,
        "label": label,
        "score": round(clamp(score, 0, 100), 1),
        "polarity": "mixed" if evidence and product.get("negativeThemes") else "positive" if evidence else "unknown",
        "sources": ["features", "details", "review"] if evidence else ["rating"],
        "evidence": evidence[:3],
    }


def review_themes(reviews: list[dict[str, Any]], features: list[str]) -> tuple[list[str], list[str]]:
    positives = [r["content"][:48] for r in reviews if r.get("rating", 0) >= 4 or r.get("sentiment") == "positive"]
    negatives = [r["content"][:48] for r in reviews if r.get("rating", 0) <= 3 or r.get("sentiment") in {"negative", "mixed"}]
    if not positives:
        positives = [f[:48] for f in features[:3]]
    return (list(dict.fromkeys(positives))[:4], list(dict.fromkeys(negatives))[:4])


def best_for(title: str, features: list[str], category: str) -> list[str]:
    text = " ".join([title, *features, category]).lower()
    out = []
    if "office" in text or "business" in text:
        out.append("Office use")
    if "travel" in text:
        out.append("Travel")
    if "adult" in text:
        out.append("Adults")
    if not out and category:
        out.append(category)
    return out[:3] or ["General shopping needs"]


def product_payload(row: dict[str, Any], include_evidence: bool = True) -> dict[str, Any]:
    product = {
        "id": row["id"],
        "brand": row["brand"],
        "name": row["name"],
        "slug": row["slug"],
        "category": row["category"],
        "description": row["description"],
        "currentPrice": row["price"],
        "originalPrice": row["original_price"],
        "currency": row["currency"],
        "stockStatus": row["stock_status"],
        "sellerType": row["seller_type"],
        "deliveryText": row["delivery_text"],
        "returnPolicy": row["return_policy"],
        "warrantyText": row["warranty_text"],
        "rating": row["rating"],
        "reviewCount": row["review_count"],
        "imageUrls": decode_json(row["image_urls"], []),
        "lastUpdatedAt": row["last_updated_at"],
        "dataUpdatedAt": row["data_updated_at"],
        "attributes": {
            "fitType": row["fit_type"],
            "inEarDepth": row["in_ear_depth"],
            "noiseCancellationScore": row["noise_cancellation_score"],
            "noiseCancellationDepth": row["noise_cancellation_depth"],
            "comfortScore": row["comfort_score"],
            "smallEarFriendly": bool(row["small_ear_friendly"]),
            "singleEarWeight": row["single_ear_weight"],
            "earTipSizes": decode_json(row["ear_tip_sizes"], []),
            "callScore": row["call_score"],
            "windNoiseScore": row["wind_noise_score"],
            "batteryHours": row["battery_hours"],
            "totalBatteryHours": row["total_battery_hours"],
            "androidCompatible": bool(row["android_compatible"]),
            "iosCompatible": bool(row["ios_compatible"]),
            "supportedCodecs": decode_json(row["supported_codecs"], []),
            "multipoint": bool(row["multipoint"]),
            "waterResistance": row["water_resistance"],
            "wirelessCharging": bool(row["wireless_charging"]),
            "transparencyMode": bool(row["transparency_mode"]),
            "appSupport": decode_json(row["app_support"], []),
            "microphoneCount": row["microphone_count"],
        },
        "positiveThemes": decode_json(row["positive_themes"], []),
        "negativeThemes": decode_json(row["negative_themes"], []),
        "bestFor": decode_json(row["best_for"], []),
        "notFor": decode_json(row["not_for"], []),
        "sourceFields": {
            "schema": PICKMATE_SCHEMA,
            "productId": row["id"],
            "title": f"{row['brand']} {row['name']}",
            "mainCategory": row["category"],
            "store": row["seller_type"],
            "brand": row["brand"],
            "price": row["price"],
            "averageRating": row["rating"],
            "ratingNumber": row["review_count"],
            "features": decode_json(row["advantages"], []),
            "description": [row["description"]],
            "details": {
                "Brand": row["brand"],
                "Category": row["category"],
                "Codec": ", ".join(decode_json(row["supported_codecs"], [])),
                "WaterResistance": row["water_resistance"],
                "BatteryHours": row["battery_hours"],
                "Weight": row["single_ear_weight"],
            },
        },
    }
    if include_evidence:
        product["priceHistory"] = price_history(row["id"])
        product["reviews"] = review_evidence(row["id"])
        product["discussions"] = discussion_evidence(row["id"])
        product["questions"] = question_evidence(row["id"])
        product["videos"] = video_evidence(row["id"])
    else:
        product["priceHistory"] = []
        product["reviews"] = []
        product["discussions"] = []
        product["questions"] = []
        product["videos"] = []
    product["standardizedDimensions"] = standardized_dimensions(product)
    return product


def price_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "date": row["date"],
        "price": row["price"],
        "promotionType": row["promotion_type"],
        "source": row["source"],
        "verifiedAt": row["verified_at"],
    }


def review_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "sourceType": row["source_type"],
        "sourceName": row["source_name"],
        "content": row["content"],
        "rating": row["rating"],
        "verifiedPurchase": bool(row["verified_purchase"]),
        "usageDuration": row["usage_duration"],
        "userProfile": row["user_profile"],
        "topics": decode_json(row["topics"], []),
        "sentiment": row["sentiment"],
        "helpfulCount": row["helpful_count"],
        "createdAt": row["created_at"],
    }


def discussion_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "sourceType": row["source_type"],
        "sourceName": row["source_name"],
        "content": row["content"],
        "topic": row["topic"],
        "sentiment": row["sentiment"],
        "userProfile": row["user_profile"],
        "createdAt": row["created_at"],
    }


def question_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "question": row["question"],
        "answer": row["answer"],
        "topic": row["topic"],
        "sentiment": row["sentiment"],
    }


def video_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "videoTitle": row["video_title"],
        "creator": row["creator"],
        "videoType": row["video_type"],
        "sourceUrl": row["source_url"],
        "timestamp": row["timestamp"],
        "findingType": row["finding_type"],
        "finding": row["finding"],
        "impactType": row["impact_type"],
        "confirmedByCount": row["confirmed_by_count"],
        "evidenceStrength": row["evidence_strength"],
        "createdAt": row["created_at"],
    }


def product_search_text(product: dict[str, Any]) -> str:
    source = product.get("sourceFields", {})
    values = [
        product.get("brand", ""),
        product.get("name", ""),
        product.get("description", ""),
        source.get("title", ""),
        source.get("mainCategory", ""),
        source.get("store", ""),
        *(source.get("features") or []),
        *(source.get("description") or []),
        *[f"{key}: {value}" for key, value in (source.get("details") or {}).items()],
        *(product.get("positiveThemes") or []),
        *(product.get("negativeThemes") or []),
    ]
    return " ".join(str(value) for value in values).lower()


def search_tokens(text: str) -> list[str]:
    stopwords = {
        "find", "me", "for", "with", "that", "the", "and", "or", "a", "an", "to", "of", "by",
        "need", "want", "looking", "searching", "reviews", "review", "mention", "mentioning",
        "预算", "以内", "以下", "推荐", "想要", "需要", "评论", "评价", "商品",
    }
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]{1,}|[\u4e00-\u9fa5]{2,}", text.lower())
    out = []
    for token in tokens:
        clean = token.strip(".-")
        if clean and clean not in stopwords and not clean.isdigit():
            out.append(clean)
    return list(dict.fromkeys(out))


def text_blob(
    title: str,
    features: list[str],
    description: list[str],
    details: dict[str, Any],
    reviews: list[dict[str, Any]],
) -> str:
    detail_text = " ".join(f"{key}: {value}" for key, value in details.items())
    review_text = " ".join(str(review.get("content", "")) for review in reviews[:20])
    return " ".join([title, *features, *description, detail_text, review_text]).lower()


def contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def keyword_score(text: str, keywords: list[str], default: float = 62) -> float:
    hits = sum(1 for keyword in keywords if keyword.lower() in text)
    return clamp(default + hits * 7, 35, 96)


def keyword_dimension(product: dict[str, Any], keywords: list[str], default: float) -> float:
    source = product.get("sourceFields", {})
    text = text_blob(
        source.get("title", product.get("name", "")),
        source.get("features") or [],
        source.get("description") or [],
        source.get("details") or {},
        product.get("reviews") or [],
    )
    return keyword_score(text, keywords, default=default)


def rating_score(rating: float, rating_number: int) -> float:
    if not rating:
        return 58
    confidence = min(10, math.log10(max(rating_number, 1)) * 3)
    return clamp(rating * 18 + confidence, 35, 100)


def review_confidence_score(product: dict[str, Any]) -> float:
    count = int(product.get("reviewCount") or 0)
    reviews = product.get("reviews") or []
    count_score = min(42, math.log10(max(count, 1)) * 14)
    verified = sum(1 for review in reviews if review.get("verifiedPurchase"))
    helpful = sum(int(review.get("helpfulCount") or 0) for review in reviews)
    return clamp(42 + count_score + min(10, verified) + min(8, helpful / 50), 35, 100)


def inferred_codecs(text: str) -> list[str]:
    codecs = [codec for codec in ["LDAC", "LHDC", "AAC", "SSC", "aptX"] if codec.lower() in text.lower()]
    return codecs or ["AAC"]


def review_topics(content: str) -> list[str]:
    topics = []
    checks = [
        ("comfort", ["comfortable", "comfort", "fit", "舒适", "佩戴"]),
        ("quality", ["quality", "well made", "质量", "品质"]),
        ("durability", ["durable", "sturdy", "broken", "broke", "耐用", "坏"]),
        ("compatibility", ["compatible", "android", "ios", "兼容"]),
        ("price_value", ["value", "price", "affordable", "性价比", "价格"]),
    ]
    for topic, keywords in checks:
        if contains_any(content, keywords):
            topics.append(topic)
    return topics or ["general_feedback"]


def review_sentiment(rating: float, content: str) -> str:
    lower = content.lower()
    if rating <= 2 or contains_any(lower, ["bad", "poor", "broken", "disappointed", "差", "坏", "失望"]):
        return "negative"
    if rating == 3 or contains_any(lower, ["but", "however", "issue", "problem", "但是", "不过", "问题"]):
        return "mixed"
    if rating >= 4:
        return "positive"
    return "neutral"


def timestamp_to_iso(value: Any) -> str:
    if not value:
        return "2026-08-06T00:00:00+00:00"
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except Exception:
        return "2026-08-06T00:00:00+00:00"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
