from __future__ import annotations

from typing import Any

from ..db import encode_json, execute, now_iso, one


def save_run(run_id: str, session_id: str, message: str, action: str, trace: dict[str, Any], response: dict[str, Any]) -> None:
    execute(
        "INSERT INTO recommendation_runs(run_id,session_id,message,action,trace_json,response_json,created_at) VALUES(?,?,?,?,?,?,?)",
        (run_id, session_id, message, action, encode_json(trace), encode_json(response), now_iso()),
    )


def get_run(run_id: str) -> dict[str, Any] | None:
    return one("SELECT * FROM recommendation_runs WHERE run_id=?", (run_id,))
