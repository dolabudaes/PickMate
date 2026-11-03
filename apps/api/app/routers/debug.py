from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import decode_json, query
from ..harness.trace import get_run

router = APIRouter()


@router.get("/recommendation-runs/{run_id}")
def recommendation_run(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(404, "Recommendation run not found")
    return decode_row(row)


@router.get("/debug/runs")
def debug_runs() -> list[dict]:
    return [decode_row(row) for row in query("SELECT * FROM recommendation_runs ORDER BY created_at DESC LIMIT 50")]


@router.get("/debug/runs/{run_id}")
def debug_run(run_id: str) -> dict:
    return recommendation_run(run_id)


def decode_row(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "session_id": row["session_id"],
        "message": row["message"],
        "action": row["action"],
        "trace": decode_json(row["trace_json"], {}),
        "response": decode_json(row["response_json"], {}),
        "created_at": row["created_at"],
    }
