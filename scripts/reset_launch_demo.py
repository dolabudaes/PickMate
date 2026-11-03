#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("PICKMATE_PRODUCT_DB_PATH", str(ROOT / "apps" / "api" / "data" / "home-audio-1000.db"))
os.environ.setdefault("PICKMATE_APP_DB_PATH", str(ROOT / "apps" / "api" / "data" / "pickmate-app.db"))
os.environ.setdefault("PICKI_AGENT_MODE", "deterministic")
os.environ.setdefault("PICKMATE_DEMO_MODE", "true")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate the launch demo session: 2 cart items and 2 Picki chats.")
    parser.add_argument("--session-id", help="Demo session id (default: pickmate-launch-demo)")
    args = parser.parse_args()

    from app.db import init_db
    from app.services.launch_demo import DEMO_SESSION_ID, seed_launch_demo_sync

    init_db()
    session_id = args.session_id or DEMO_SESSION_ID
    result = seed_launch_demo_sync(session_id)
    print(f"Demo session: {result['session_id']}")
    print(f"Conversations: {result['conversations']}")
    print(f"Cart: {result['cart_ids']}")
    print(f"Saved: {result['saved_ids']}")
    for pid, meta in result["products"].items():
        print(f"  {pid}  ${meta['price']}  {meta['name'][:70]}")


if __name__ == "__main__":
    main()
