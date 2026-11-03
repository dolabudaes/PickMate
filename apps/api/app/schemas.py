from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Action = Literal["recommend", "compare", "decide", "price_check", "product_question", "preference_update"]


class SessionProfile(BaseModel):
    budget: dict[str, int | None] = Field(default_factory=lambda: {"max": None})
    use_cases: list[str] = Field(default_factory=list)
    device_platform: Literal["android", "ios", "any"] = "any"
    priorities: dict[str, float] = Field(default_factory=lambda: {
        "noise_cancellation": 0.45,
        "comfort": 0.45,
        "call_quality": 0.4,
        "battery": 0.4,
        "price_value": 0.6,
        "compatibility": 0.7,
        "quality": 0.62,
        "durability": 0.48,
        "review_confidence": 0.55,
    })
    small_ear_friendly: bool = False
    dealbreakers: list[str] = Field(default_factory=list)
    explicit_concerns: list[str] = Field(default_factory=list)
    accepted_tradeoffs: list[str] = Field(default_factory=list)
    budget_preference: Literal["strict", "flexible", "quality_first", "unknown"] = "unknown"
    risk_preference: Literal["risk_averse", "balanced", "risk_tolerant", "unknown"] = "balanced"
    preferences: list[dict[str, Any]] = Field(default_factory=list)
    observed_signals: list[dict[str, Any]] = Field(default_factory=list)
    decision_history: dict[str, list[str]] = Field(default_factory=lambda: {
        "view": [],
        "compare": [],
        "save": [],
        "choose": [],
        "reject": [],
    })
    category_preferences: dict[str, dict[str, float]] = Field(default_factory=dict)
    shopping_style: list[str] = Field(default_factory=list)


class HarnessRequest(BaseModel):
    session_id: str
    action: Action = "recommend"
    message: str = ""
    current_product_id: str | None = None
    candidate_product_ids: list[str] = Field(default_factory=list)
    exclude_product_ids: list[str] = Field(default_factory=list)
    prefer_terms: list[str] = Field(default_factory=list)
    max_price: float | None = None


class HarnessResponse(BaseModel):
    run_id: str
    intent: dict[str, Any]
    primary: dict[str, Any] | None
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    regret_guard: dict[str, Any] | str
    switch_conditions: list[dict[str, Any]] = Field(default_factory=list)
    clarification: str | None = None
    fallback_used: bool = False
    trace_id: str
    excluded_products: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: str = ""
    missing_information: list[str] = Field(default_factory=list)
    data_updated_at: str = "2026-08-06"
    used_preferences: list[str] = Field(default_factory=list)


class SessionCreateOut(BaseModel):
    session_id: str
    profile: SessionProfile


class EventIn(BaseModel):
    session_id: str
    name: str
    product_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PickiIn(BaseModel):
    session_id: str
    message: str = ""
    current_product_id: str | None = None
    candidate_product_ids: list[str] = Field(default_factory=list)


class DecisionIn(BaseModel):
    session_id: str
    user_need: str
    result: dict[str, Any]


class PickTurnIn(BaseModel):
    session_id: str
    conversation_id: str
    message: str = ""
    action: Literal["message", "cheaper", "different_style", "compare", "why_this", "focus", "promote"] = "message"
    product_id: str | None = None


class MemoryToggleIn(BaseModel):
    session_id: str
    enabled: bool


class CartIn(BaseModel):
    session_id: str
    product_id: str
    conversation_id: str | None = None
    source_type: Literal["chat", "product"] = "product"


class TasteIn(BaseModel):
    session_id: str
    label: str


class TastePatchIn(BaseModel):
    session_id: str
    normalized_preference: str | None = None
    label: str | None = None
    status: str | None = None
    user_confirmed: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)


class AgentActionConfirmIn(BaseModel):
    session_id: str
    conversation_id: str | None = None
    type: Literal["cart_update", "preference_update"]
    payload: dict[str, Any] = Field(default_factory=dict)


class ComparisonIn(BaseModel):
    session_id: str
    product_ids: list[str]


class ComparisonLinkIn(BaseModel):
    session_id: str
    conversation_id: str


class SavePickIn(BaseModel):
    session_id: str
    conversation_id: str | None = None
    product_id: str
    reason: str = ""


class PreferenceIn(BaseModel):
    session_id: str
    preference: str
    value: Any | None = None
    weight: float | None = None
    source: Literal["explicit", "confirmed", "decision_history", "behavior_inferred"] = "explicit"
    confidence: float = 0.9
    scope: Literal["session", "long_term", "category", "observed"] = "long_term"
    category: str | None = None
