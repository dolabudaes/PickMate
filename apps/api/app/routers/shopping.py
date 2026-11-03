from __future__ import annotations

from fastapi import APIRouter, Query

from ..harness.agent_harness import execute_confirmed_action
from ..schemas import AgentActionConfirmIn, CartIn, ComparisonIn, ComparisonLinkIn, MemoryToggleIn, PickTurnIn, SavePickIn, TasteIn
from ..services.shopping_loop import add_cart_item, add_note_memory, conversations_for_product, conversations_for_products, create_comparison, forget_memory, link_comparison, list_cart, list_comparisons, list_memories, list_saved, memory_enabled, remove_cart_item, remove_saved, run_turn, save_pick, set_memory_enabled

router = APIRouter()


@router.get("/demo/status")
def demo_status() -> dict:
    from ..services.launch_demo import demo_status as status
    return status()


@router.post("/demo/reset")
async def demo_reset() -> dict:
    from ..services.launch_demo import DEMO_SESSION_ID, seed_launch_demo
    return await seed_launch_demo(DEMO_SESSION_ID, force=True)


@router.post("/picki/turn")
async def picki_turn(body: PickTurnIn) -> dict:
    return await run_turn(body.session_id, body.conversation_id, body.message, body.action, body.product_id)


@router.post("/picki/actions/execute")
def execute_agent_action(body: AgentActionConfirmIn) -> dict:
    return execute_confirmed_action(body.session_id, body.model_dump())


@router.get("/shopping/memories")
def memories(session_id: str = Query(...)) -> dict:
    from ..services.launch_demo import ensure_demo_persona_preferences

    ensure_demo_persona_preferences(session_id)
    return {"memory_enabled": memory_enabled(session_id), "items": list_memories(session_id)}


@router.delete("/shopping/memories/{memory_id}")
def delete_memory(memory_id: str, session_id: str = Query(...)) -> dict:
    from ..services.taste_consolidator import delete_taste

    if delete_taste(session_id, memory_id):
        return {"id": memory_id, "enabled": False}
    return forget_memory(session_id, memory_id)


@router.put("/shopping/memory")
def toggle_memory(body: MemoryToggleIn) -> dict:
    return set_memory_enabled(body.session_id, body.enabled)


@router.get("/shopping/saves")
def saves(session_id: str = Query(...)) -> list[dict]:
    return list_saved(session_id)


@router.post("/shopping/saves")
def create_save(body: SavePickIn) -> dict:
    return save_pick(body.session_id, body.conversation_id, body.product_id, body.reason)


@router.delete("/shopping/saves/{product_id}")
def delete_save(product_id: str, session_id: str = Query(...)) -> dict:
    return remove_saved(session_id, product_id)


@router.get("/shopping/cart")
def cart(session_id: str = Query(...)) -> list[dict]:
    return list_cart(session_id)


@router.post("/shopping/cart")
def create_cart_item(body: CartIn) -> dict:
    return add_cart_item(body.session_id, body.product_id, body.conversation_id, body.source_type)


@router.delete("/shopping/cart/{product_id}")
def delete_cart_item(product_id: str, session_id: str = Query(...)) -> dict:
    return remove_cart_item(session_id, product_id)


@router.post("/shopping/memories")
def create_memory(body: TasteIn) -> dict:
    return add_note_memory(body.session_id, body.label)


@router.get("/shopping/comparisons")
def comparisons(session_id: str = Query(...)) -> list[dict]:
    return list_comparisons(session_id)


@router.post("/shopping/comparisons")
def new_comparison(body: ComparisonIn) -> dict:
    return create_comparison(body.session_id, body.product_ids)


@router.post("/shopping/comparisons/{comparison_id}/conversation")
def attach_comparison(comparison_id: str, body: ComparisonLinkIn) -> dict:
    return link_comparison(body.session_id, comparison_id, body.conversation_id)


@router.get("/shopping/products/{product_id}/conversations")
def product_conversations(product_id: str, session_id: str = Query(...)) -> list[dict]:
    return conversations_for_product(session_id, product_id)


@router.get("/shopping/related-conversations")
def related_conversations(session_id: str = Query(...), product_ids: list[str] = Query(...)) -> list[dict]:
    return conversations_for_products(session_id, product_ids)
