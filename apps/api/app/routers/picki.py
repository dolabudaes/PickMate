from __future__ import annotations

from fastapi import APIRouter

from ..harness.harness import PickMateHarness
from ..schemas import HarnessRequest, HarnessResponse, PickiIn

router = APIRouter()
harness = PickMateHarness()


@router.post("/picki/recommend")
async def recommend(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="recommend"))


@router.post("/picki/update")
async def update(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="preference_update"))


@router.post("/picki/compare")
async def compare(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="compare"))


@router.post("/picki/decide")
async def decide(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="decide"))


@router.post("/picki/price-check")
async def price_check(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="price_check"))


@router.post("/picki/product-question")
async def product_question(body: PickiIn) -> HarnessResponse:
    return await harness.run(HarnessRequest(**body.model_dump(), action="product_question"))
