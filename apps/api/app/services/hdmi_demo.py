from __future__ import annotations

from typing import Any

from .launch_demo import (
    BASICS_ID as HDMI_CHEAPER_ASIN,
    DEMO_CONV_GAMING as DEMO_CONV_CABLE,
    DEMO_CONV_MONITOR,
    DVI_ID as HDMI_DVI_ASIN,
    KABEL_ID as HDMI_PRIMARY_ASIN,
    reset_demo_session,
    resolve_demo_products,
    seed_launch_demo,
    seed_launch_demo_sync,
)


def resolve_hdmi_primary_id() -> str:
    resolve_demo_products()
    return HDMI_PRIMARY_ASIN


def prune_non_demo_chats() -> int:
    return 0


async def seed_hdmi_demo_chats(session_id: str) -> dict[str, Any]:
    result = await seed_launch_demo(session_id)
    return {
        "session_id": result["session_id"],
        "conversations": result["conversations"],
        "product_id": HDMI_PRIMARY_ASIN,
    }


def seed_hdmi_demo_chats_sync(session_id: str) -> dict[str, Any]:
    return seed_launch_demo_sync(session_id)
