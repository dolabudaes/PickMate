from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceKind = Literal[
    "verified_catalog_fact",
    "manufacturer_claim",
    "customer_review_opinion",
    "model_analysis",
    "missing_or_uncertain",
]

ActionLifecycle = Literal["proposed", "validated", "confirmed", "executed", "failed"]


class ProposedAction(BaseModel):
    id: str
    type: Literal["cart_update", "preference_update"]
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ActionLifecycle = "proposed"


class StructuredAgentResponse(BaseModel):
    message: str = ""
    response_mode: str | None = None
    primary_message: str | None = None
    key_facts: list[dict[str, Any]] = Field(default_factory=list)
    product_refs: list[dict[str, Any]] = Field(default_factory=list)
    detail_sections: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    direct_recommendation: str | None = None
    product_highlights: list[str] = Field(default_factory=list)
    technical_specifications: list[str] = Field(default_factory=list)
    price_value_analysis: str | None = None
    customer_review_summary: str | None = None
    product_comparisons: str | None = None
    important_drawbacks: list[str] = Field(default_factory=list)
    suggested_follow_up_questions: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    response_type: str | None = None
    comparison_data: dict[str, Any] | None = None
    clarification_options: list[dict[str, Any]] = Field(default_factory=list)
    decision_highlight: str | None = None
    evidence_status: str | None = None
    decision_brief: dict[str, Any] | None = None


class AgentTurnTrace(BaseModel):
    run_id: str
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0
    errors: list[str] = Field(default_factory=list)
    evidence_validation_failures: list[str] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_actions: list[dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
