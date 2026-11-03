#!/usr/bin/env python3
"""Read-only sample of 1000 Home Audio & Theater products from product.db."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "database" / "EComAgentBench_" / "data" / "products" / "product.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "apps" / "api" / "data" / "home-audio-1000.db"
CATEGORY = "Home Audio & Theater"
TARGET = 1000

TYPE_QUOTAS = [
    ("soundbar", re.compile(r"sound\s*bar", re.I), 160),
    ("speaker", re.compile(r"\bspeakers?\b", re.I), 180),
    ("receiver", re.compile(r"\breceivers?\b", re.I), 120),
    ("amplifier", re.compile(r"amplifier|\bamps?\b", re.I), 100),
    ("theater", re.compile(r"home\s*theat|surround", re.I), 100),
    ("cable", re.compile(r"hdmi|optical|toslink|\bcables?\b", re.I), 80),
    ("headphone", re.compile(r"headphone|earbud|headset", re.I), 80),
]


def has_image(data_json: str) -> bool:
    if not data_json:
        return False
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        return "http" in data_json and "image" in data_json.lower()
    blob = json.dumps(data.get("images") or data.get("image") or data.get("hi_res") or "")
    return "http" in blob


def connect_source(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def classify(title: str) -> str:
    for name, pattern, _quota in TYPE_QUOTAS:
        if pattern.search(title or ""):
            return name
    return "other"


def sample_rows(source: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    candidates = source.execute(
        """
        SELECT * FROM products
        WHERE main_category=? AND has_price=1 AND price IS NOT NULL
        ORDER BY rating_number DESC, average_rating DESC
        LIMIT 8000
        """,
        (CATEGORY,),
    ).fetchall()
    buckets: dict[str, list[sqlite3.Row]] = {name: [] for name, _, _ in TYPE_QUOTAS}
    buckets["other"] = []
    for row in candidates:
        if not has_image(row["data"]):
            continue
        buckets[classify(row["title"])].append(row)

    chosen: list[sqlite3.Row] = []
    seen: set[str] = set()
    for name, _pattern, quota in TYPE_QUOTAS:
        for row in buckets[name][:quota]:
            if row["product_id"] not in seen:
                chosen.append(row)
                seen.add(row["product_id"])
    leftover_quota = limit - len(chosen)
    preferred = [row for row in buckets["other"] if row["product_id"] not in seen]
    preferred_ids = {row["product_id"] for row in preferred}
    rest = [
        row
        for row in candidates
        if row["product_id"] not in seen and row["product_id"] not in preferred_ids and has_image(row["data"])
    ]
    for row in preferred + rest:
        if leftover_quota <= 0:
            break
        if row["product_id"] in seen:
            continue
        chosen.append(row)
        seen.add(row["product_id"])
        leftover_quota -= 1
    return chosen[:limit]


def write_subset(rows: list[sqlite3.Row], source: sqlite3.Connection, output: Path) -> None:
    if output.exists():
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    dest = sqlite3.connect(output)
    dest.execute("PRAGMA journal_mode=WAL")
    product_sql = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'").fetchone()[0]
    dest.execute(product_sql)
    columns = [row[1] for row in source.execute("PRAGMA table_info(products)")]
    dest.executemany(
        f"INSERT INTO products ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        [tuple(row[col] for col in columns) for row in rows],
    )
    dest.execute("CREATE INDEX IF NOT EXISTS idx_brand ON products(brand COLLATE NOCASE)")
    dest.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(main_category)")
    dest.execute("CREATE INDEX IF NOT EXISTS idx_store ON products(store)")
    dest.execute("CREATE VIRTUAL TABLE products_fts USING fts5(title, content='products')")
    dest.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")

    ids = [row["product_id"] for row in rows]
    review_sql_row = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reviews'").fetchone()
    if review_sql_row:
        dest.execute(review_sql_row[0])
        review_cols = [row[1] for row in source.execute("PRAGMA table_info(reviews)")]
        chunk = 200
        for i in range(0, len(ids), chunk):
            part = ids[i : i + chunk]
            found = source.execute(
                f"SELECT * FROM reviews WHERE product_id IN ({','.join('?' for _ in part)})",
                part,
            ).fetchall()
            if found:
                dest.executemany(
                    f"INSERT INTO reviews ({', '.join(review_cols)}) VALUES ({', '.join('?' for _ in review_cols)})",
                    [tuple(item[col] for col in review_cols) for item in found],
                )
        dest.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id)")
    dest.commit()
    dest.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=TARGET)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Refusing to write onto the source product.db")
    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")
    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists. Pass --force to replace the subset only.")
    source = connect_source(args.source)
    rows = sample_rows(source, args.limit)
    if len(rows) < args.limit:
        raise SystemExit(f"Only found {len(rows)} eligible Home Audio products with images/prices")
    write_subset(rows, source, args.output)
    source.close()
    print(f"Wrote {len(rows)} Home Audio & Theater products to {args.output}")
    print("Source product.db was not modified.")


if __name__ == "__main__":
    main()
