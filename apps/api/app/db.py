from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
AUTHORIZED_CATEGORY = "Home Audio & Theater"
DEFAULT_PRODUCT_DB_PATH = DATA_DIR / "home-audio-1000.db"
DEFAULT_APP_DB_PATH = DATA_DIR / "pickmate-app.db"
DEFAULT_DB_PATH = DEFAULT_PRODUCT_DB_PATH


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def is_ecomagentbench_product_db_path(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            rows = conn.execute("PRAGMA table_info(products)").fetchall()
    except Exception:
        return False
    columns = {row[1] for row in rows}
    return "product_id" in columns and "data" in columns and "id" not in columns


def configured_product_db_path() -> tuple[Path, str]:
    if os.getenv("PICKMATE_PRODUCT_DB_PATH"):
        return _expand(os.environ["PICKMATE_PRODUCT_DB_PATH"]), "PICKMATE_PRODUCT_DB_PATH"
    for name in ("PICKMATE_DB_PATH", "SQLITE_PATH"):
        value = os.getenv(name)
        if value and is_ecomagentbench_product_db_path(_expand(value)):
            return _expand(value), name
    return DEFAULT_PRODUCT_DB_PATH, "default_product_db"


def configured_app_db_path() -> tuple[Path, str]:
    if os.getenv("PICKMATE_APP_DB_PATH"):
        return _expand(os.environ["PICKMATE_APP_DB_PATH"]), "PICKMATE_APP_DB_PATH"
    configured = [
        (name, os.environ[name])
        for name in ("SQLITE_PATH", "SQLLTE_PATH")
        if os.getenv(name)
    ]
    distinct_paths = {str(_expand(value).resolve()) for _, value in configured}
    if len(distinct_paths) > 1:
        names = ", ".join(name for name, _ in configured)
        raise RuntimeError(f"Conflicting application database paths are configured via: {names}")
    if configured:
        path = _expand(configured[0][1])
        if not is_ecomagentbench_product_db_path(path):
            return path, configured[0][0]
    return DEFAULT_APP_DB_PATH, "default_app_db"


def configured_db_path() -> tuple[Path, str]:
    return configured_app_db_path()


PRODUCT_DB_PATH, PRODUCT_DB_PATH_SOURCE = configured_product_db_path()
APP_DB_PATH, APP_DB_PATH_SOURCE = configured_app_db_path()
DB_PATH, DB_PATH_SOURCE = APP_DB_PATH, APP_DB_PATH_SOURCE

DATA_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def product_db() -> sqlite3.Connection:
    if not PRODUCT_DB_PATH.exists():
        raise RuntimeError(f"Authorized product.db was not found at {PRODUCT_DB_PATH}")
    uri = f"file:{PRODUCT_DB_PATH.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def product_query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with product_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def product_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = product_query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    with db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_db() -> None:
    if is_ecomagentbench_product_db_path(APP_DB_PATH):
        raise RuntimeError(
            "The application database path points at the read-only Amazon product.db. "
            "Set PICKMATE_APP_DB_PATH to a writable file such as apps/api/data/pickmate-app.db."
        )
    ddl = [
        """CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS browsing_events (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL, product_id TEXT,
            metadata TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS decision_profiles (
            session_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS recommendation_runs (
            run_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, message TEXT, action TEXT, trace_json TEXT NOT NULL,
            response_json TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS saved_decisions (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_need TEXT, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS decision_sessions (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, state_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS picki_conversations (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, title TEXT NOT NULL,
            state_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS demo_conversation_archives (
            conversation_id TEXT NOT NULL, session_id TEXT NOT NULL,
            snapshot_json TEXT NOT NULL, archive_reason TEXT NOT NULL,
            archived_at TEXT NOT NULL, PRIMARY KEY (conversation_id, session_id)
        )""",
        """CREATE TABLE IF NOT EXISTS shopping_sessions (
            conversation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            state_json TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS preference_memories (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, facet TEXT NOT NULL, value TEXT NOT NULL,
            label TEXT NOT NULL, scope TEXT NOT NULL, confidence REAL NOT NULL, evidence TEXT,
            source TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS shopping_settings (
            session_id TEXT PRIMARY KEY, memory_enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS saved_picks (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, product_id TEXT NOT NULL,
            conversation_id TEXT, reason TEXT, title TEXT, price REAL, created_at TEXT NOT NULL,
            UNIQUE(session_id, product_id)
        )""",
        """CREATE TABLE IF NOT EXISTS interaction_events (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, conversation_id TEXT,
            product_id TEXT, event_type TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS cart_items (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, product_id TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(session_id, product_id)
        )""",
        """CREATE TABLE IF NOT EXISTS cart_item_provenance (
            id TEXT PRIMARY KEY, cart_item_id TEXT NOT NULL, conversation_id TEXT,
            source_type TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS conversation_products (
            conversation_id TEXT NOT NULL, session_id TEXT NOT NULL, product_id TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY (conversation_id, product_id)
        )""",
        """CREATE TABLE IF NOT EXISTS comparisons (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, title TEXT NOT NULL,
            verdict TEXT NOT NULL, winner_product_id TEXT, conversation_id TEXT,
            products_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
    ]
    with db() as conn:
        for sql in ddl:
            conn.execute(sql)
        conn.commit()
    from .services.taste_schema import migrate_taste_schema

    migrate_taste_schema()


def seed_dev_data() -> None:
    if is_ecomagentbench_product_db():
        return
    raise RuntimeError(
        f"PickMate requires the Home Audio 1000-product catalog at {DEFAULT_PRODUCT_DB_PATH}."
    )


def database_config() -> dict[str, Any]:
    return {
        "path": str(PRODUCT_DB_PATH),
        "source": PRODUCT_DB_PATH_SOURCE,
        "app_path": str(APP_DB_PATH),
        "app_source": APP_DB_PATH_SOURCE,
        "catalog": "amazon_home_audio",
        "category": AUTHORIZED_CATEGORY,
    }


def english_seed_product(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "stock": "In stock",
        "scene": "Commuting, office work, and everyday listening",
        "advantages": [
            f"Noise cancellation score: {item['noiseCancellationScore']}",
            f"Supports {item.get('androidCodec', 'AAC')}",
            f"Battery life up to {item['batteryHours']} hours",
        ],
        "limitations": [
            "Call quality is not category-leading" if int(item["callScore"]) < 84 else "Touch controls can be triggered accidentally",
            "Fit feedback is mixed for smaller ears" if not item.get("smallEarFriendly") else "The charging case can show fine scratches",
        ],
        "reviewHighlights": ["Useful noise cancellation", "Stable fit", "Reliable connection"],
        "reviewComplaints": [
            "Call quality is average" if int(item["callScore"]) < 84 else "Touch controls can be triggered accidentally",
            "The charging case can show fine scratches",
        ],
    }


def is_ecomagentbench_product_db() -> bool:
    return is_ecomagentbench_product_db_path(PRODUCT_DB_PATH)


def is_pickmate_subset_db() -> bool:
    return False


def is_external_product_db() -> bool:
    return is_ecomagentbench_product_db()


def supplemental_products() -> list[dict[str, Any]]:
    rows = [
        ("samsung-galaxy-buds-fe", "Samsung", "Galaxy Buds FE", 499, 699, 4.4, 7300, 80, 82, 80, 8, 5.6, "SSC", False),
        ("samsung-galaxy-buds2-pro", "Samsung", "Galaxy Buds2 Pro", 899, 1299, 4.6, 9000, 89, 86, 88, 5, 5.5, "SSC", True),
        ("sony-wf-c700n", "Sony", "WF-C700N", 499, 799, 4.4, 5600, 78, 88, 78, 7.5, 4.6, "AAC", True),
        ("sony-wf-1000xm5", "Sony", "WF-1000XM5", 1299, 1999, 4.8, 15000, 98, 90, 90, 8, 5.9, "LDAC", True),
        ("vivo-tws-4-hifi", "vivo", "TWS 4 Hi-Fi", 499, 599, 4.5, 4700, 84, 85, 82, 11, 4.8, "LDAC", True),
        ("vivo-tws-3-pro", "vivo", "TWS 3 Pro", 699, 999, 4.5, 5500, 88, 84, 83, 6.8, 5.2, "LDAC", True),
        ("xiaomi-buds-5-pro", "Xiaomi", "Buds 5 Pro", 699, 899, 4.6, 6200, 88, 84, 86, 8, 5.2, "LHDC", True),
        ("xiaomi-redmi-buds-6", "Xiaomi", "Redmi Buds 6", 249, 329, 4.3, 16800, 70, 76, 70, 7, 4.9, "AAC", False),
        ("huawei-freebuds-pro-3", "Huawei", "FreeBuds Pro 3", 999, 1499, 4.7, 11000, 94, 86, 92, 6.5, 5.8, "L2HC", True),
        ("oppo-enco-x3", "OPPO", "Enco X3", 899, 1299, 4.7, 4200, 92, 88, 88, 10, 4.9, "LHDC", True),
        ("oneplus-buds-pro-3", "OnePlus", "Buds Pro 3", 799, 999, 4.6, 3900, 90, 86, 86, 10, 4.9, "LHDC", True),
        ("realme-buds-t300", "realme", "Buds T300", 229, 299, 4.2, 12000, 65, 74, 66, 8, 4.7, "AAC", False),
        ("edifier-neobuds-pro-2", "Edifier", "NeoBuds Pro 2", 599, 899, 4.5, 4500, 90, 80, 82, 5.5, 5.6, "LDAC", False),
        ("jbl-tour-pro-2", "JBL", "Tour Pro 2", 999, 1499, 4.5, 2800, 88, 82, 86, 10, 6.1, "AAC", False),
        ("soundcore-p40i", "Soundcore", "P40i", 299, 399, 4.4, 8200, 74, 80, 75, 12, 5.0, "AAC", True),
        ("soundcore-a30i", "Soundcore", "A30i", 239, 299, 4.3, 5400, 68, 82, 68, 7, 4.2, "AAC", True),
        ("nothing-ear-2024", "Nothing", "Ear", 899, 1099, 4.6, 3500, 88, 87, 84, 8.5, 4.6, "LDAC", True),
        ("honor-earbuds-x7", "Honor", "Earbuds X7", 199, 249, 4.2, 10000, 55, 78, 62, 9, 4.3, "AAC", True),
    ]
    out = []
    for pid, brand, name, price, original, rating, review_count, noise, comfort, call, battery, weight, codec, small in rows:
        out.append({
            "id": pid,
            "brand": brand,
            "name": f"{brand} {name}" if brand not in name else name,
            "price": price,
            "originalPrice": original,
            "recentAveragePrice": round((price + original) / 2),
            "stock": "In stock",
            "rating": rating,
            "reviewCount": review_count,
            "image": f"earbuds-{pid}",
            "scene": "Commuting, office work, and everyday listening",
            "noiseCancellationScore": noise,
            "comfortScore": comfort,
            "callScore": call,
            "batteryHours": battery,
            "weight": weight,
            "androidCodec": codec,
            "earTipSizes": ["XS", "S", "M", "L"] if small else ["S", "M", "L"],
            "smallEarFriendly": small,
            "advantages": ["Active noise cancellation", f"Supports {codec}", "Suitable for everyday commuting"],
            "limitations": ["Call quality is not category-leading" if call < 84 else "Touch controls can be triggered accidentally", "Fit feedback is mixed for smaller ears" if not small else "The charging case can show fine scratches"],
            "reviewHighlights": ["Useful noise cancellation", "Stable fit", "Reliable connection"],
            "reviewComplaints": ["Call quality is average" if call < 84 else "Touch controls can be triggered accidentally", "The charging case can show fine scratches"],
        })
    return out


def seed_product(item: dict[str, Any]) -> None:
    product_id = item["id"]
    price = int(item["price"])
    recent_avg = int(item.get("recentAveragePrice") or price)
    noise = int(item["noiseCancellationScore"])
    comfort = int(item["comfortScore"])
    call = int(item["callScore"])
    battery_hours = float(item["batteryHours"])
    small = bool(item["smallEarFriendly"])
    codecs = [item.get("androidCodec", "AAC"), "AAC"]
    codecs = list(dict.fromkeys([c for c in codecs if c]))
    stock = "out_of_stock" if str(item.get("stock", "")).lower() == "out of stock" else "in_stock"
    limitations = item.get("limitations", [])
    advantages = item.get("advantages", [])
    price_value = max(45, min(100, round(100 - price / max(recent_avg, 1) * 20 + (recent_avg - price) / 4)))
    compatibility = 95 if any(c in codecs for c in ("LDAC", "LHDC")) else 76
    reliability = max(55, min(96, round(item.get("rating", 4.3) * 18 + min(item.get("reviewCount", 0), 15000) / 1500)))
    execute(
        """INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            product_id, item["brand"], item["name"], product_id, "tws_anc_earbuds",
            f"{item['name']} true wireless noise-cancelling earbuds from the PickMate MVP catalog.", price, int(item["originalPrice"]),
            "CNY", stock, "Official brand store", "Next-day delivery", "7-day returns", "One-year official warranty", float(item["rating"]),
            int(item["reviewCount"]), encode_json([item.get("image", product_id)]), now_iso(), "2026-08-06",
            noise, comfort, call, round(battery_hours * 8), price_value, compatibility, reliability,
            round(noise / 2), "in_ear", "shallow" if small else "medium", int(small), float(item["weight"]),
            1, 1, encode_json(codecs), encode_json(item.get("earTipSizes", ["S", "M", "L"])),
            max(50, call - 8), battery_hours, max(16, round(battery_hours * 4)), 1 if price >= 299 else 0,
            "IP54", 1 if price >= 599 else 0, 1 if noise > 65 else 0, encode_json([item["brand"], "Android"]),
            6 if call >= 86 else 4 if call >= 78 else 2, encode_json(advantages), encode_json(limitations),
            encode_json(item.get("reviewHighlights", [])), encode_json(item.get("reviewComplaints", [])),
            encode_json([item.get("scene", "Everyday commuting")]), encode_json(limitations[:2]),
        ),
    )
    seed_price_history(product_id, price, recent_avg)
    seed_reviews(product_id, item)
    seed_discussions(product_id, item)
    seed_questions(product_id, item)
    seed_videos(product_id, item)


def seed_price_history(product_id: str, price: int, avg90: int) -> None:
    offsets = [86, 73, 60, 48, 36, 25, 18, 12, 7, 3, 1, 0]
    for idx, offset in enumerate(offsets):
        month = "05" if offset > 60 else "06" if offset > 30 else "07" if offset > 10 else "08"
        day = str(max(1, 28 - (offset % 28))).zfill(2)
        seasonal = round((idx % 5 - 2) * 7)
        point_price = price if idx == len(offsets) - 1 else max(169, avg90 + seasonal - idx)
        execute(
            "INSERT INTO price_history VALUES (?,?,?,?,?,?,?)",
            (f"{product_id}-price-{idx}", product_id, f"2026-{month}-{day}", point_price, "platform_coupon" if idx > 8 else "daily_price", "MVP sample price history", "2026-08-06"),
        )


def seed_reviews(product_id: str, item: dict[str, Any]) -> None:
    positives = item.get("reviewHighlights", ["Suitable for daily use", "Reliable connection"])
    negatives = item.get("reviewComplaints", item.get("limitations", ["Limited feedback"]))
    small_text = "feedback from users with smaller ears is generally positive" if item.get("smallEarFriendly") else "fit feedback from users with smaller ears is mixed"
    for idx in range(18):
        negative = idx % 5 == 0
        topics = negatives if negative else positives
        content = f"{topics[idx % len(topics)]}; {small_text}."
        execute(
            "INSERT INTO review_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{product_id}-review-{idx}", product_id, "long_term" if idx > 12 else "platform", "Long-term user feedback" if idx > 12 else "Platform review", content, 3 if negative else 5, 1, "More than two weeks" if idx > 12 else "Within three days", "Android user with smaller ears" if idx % 3 == 0 else "Commuter", encode_json(topics), "negative" if negative else "positive", 10 + idx * 3, f"2026-07-{str(1 + idx % 26).zfill(2)}"),
        )


def seed_discussions(product_id: str, item: dict[str, Any]) -> None:
    for idx, topic in enumerate(["Smaller-ear fit", "Android codec", "Conference calls", "Subway noise cancellation", "Warranty support"]):
        weak_call = topic == "Conference calls" and int(item["callScore"]) < 82
        execute(
            "INSERT INTO discussion_evidence VALUES (?,?,?,?,?,?,?,?,?)",
            (f"{product_id}-discussion-{idx}", product_id, "community" if idx == 0 else "qa", "Long-term discussion" if idx == 0 else "Product Q&A", "Call quality is usable but not a strength; frequent meetings warrant caution." if weak_call else f"Feedback on {topic.lower()} is broadly consistent with the product specifications.", topic, "mixed" if weak_call else "neutral", "MVP sample user", f"2026-07-{str(5 + idx).zfill(2)}"),
        )


def seed_questions(product_id: str, item: dict[str, Any]) -> None:
    rows = [
        ("Is the fit comfortable for smaller ears?", "Most users with smaller ears report an acceptable fit." if item.get("smallEarFriendly") else "Feedback from users with smaller ears is mixed, so try with caution.", "fit"),
        ("How is the sound quality on Android?", f"Supports {item.get('androidCodec', 'AAC')} and is compatible with Android.", "android"),
        ("Are conference calls clear?", "Call quality is above average and more stable indoors." if int(item["callScore"]) >= 84 else "Calls are not a strength, and clarity drops in windy conditions.", "call"),
    ]
    for idx, (question, answer, topic) in enumerate(rows):
        execute("INSERT INTO product_questions VALUES (?,?,?,?,?,?)", (f"{product_id}-q-{idx}", product_id, question, answer, topic, "mixed" if "mixed" in answer or "not a strength" in answer else "positive"))


def seed_videos(product_id: str, item: dict[str, Any]) -> None:
    call = int(item["callScore"])
    rows = [
        ("Appearance after two weeks", "durability", "The charging case can develop fine scratches", "wear_issue", "appearance_only", 6),
        ("Long-term fit test", "long_term", "Adjusting the fit can trigger touch controls", "interaction_issue", "minor_interaction", 4),
        ("Call quality test", "call", "Call clarity drops in outdoor wind", "call_quality_issue", "scenario_dependent", 5 if call < 82 else 2),
    ]
    for idx, (title, video_type, finding, finding_type, impact_type, count) in enumerate(rows):
        execute(
            "INSERT INTO video_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{product_id}-video-{idx}", product_id, title, "MVP sample video", video_type, "mvp://video-evidence", f"0{idx + 1}:2{idx}", finding_type, finding, impact_type, count, "strong" if count >= 5 else "medium", "2026-08-06"),
        )
