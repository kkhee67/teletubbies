from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class GuaranteeStatus(str, Enum):
    estimated_eligible = "estimated_eligible"
    officially_eligible = "officially_eligible"
    applied = "applied"
    enrolled = "enrolled"
    ineligible = "ineligible"
    unknown = "unknown"


GUARANTEE_STATUS_VALUES = {status.value for status in GuaranteeStatus}


class AnalyzeRequest(BaseModel):
    property_id: str = Field(min_length=2, max_length=20)
    address_query: Optional[str] = Field(default=None, max_length=200)
    planned_deposit: int = Field(gt=0)
    monthly_rent: int = Field(default=0, ge=0)
    guarantee_product_type: Literal["jeonse_return", "rental_deposit", "unknown"] | None = None
    user_note: str = Field(default="", max_length=1000)
    user_corrections: dict[str, str | int | bool] = Field(default_factory=dict)


class SimulateRequest(BaseModel):
    current: AnalyzeRequest
    changed: AnalyzeRequest


class PropertySearchItem(BaseModel):
    property_id: str
    address_display: str
    district: str
    housing_type: str
    reference_value: int
    guarantee_status: GuaranteeStatus
    guarantee_product_type: Literal["jeonse_return", "rental_deposit", "unknown"]


class PropertySearchResponse(BaseModel):
    items: list[PropertySearchItem]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


GuaranteeGroup = Literal["check_required", "in_progress", "protected", "deep_analysis"]
GuaranteeProductType = Literal["jeonse_return", "rental_deposit", "unknown"]
AiApiStatus = Literal["ok", "disabled", "unavailable", "timeout", "error", "local_mock"]


class GuaranteeResponse(BaseModel):
    status: GuaranteeStatus
    group: GuaranteeGroup
    display_text: str
    message: str
    next_actions: list[str]


class CategoryScore(BaseModel):
    score: int
    max_score: int


class RiskSignal(BaseModel):
    code: str
    title: str
    severity: str
    explanation: str | None = None
    action: str
    included_in_risk_score: bool


class PropertySummary(BaseModel):
    property_id: str | None = None
    address_display: str | None = None
    district: str | None = None
    housing_type: str | None = None
    reference_value: int
    planned_deposit: int
    monthly_rent: int
    deposit_ratio: float | None = None
    mortgage_status: str | None = None
    seizure_status: str | None = None
    joint_collateral: str | None = None
    guarantee_status: GuaranteeStatus
    guarantee_product_type: GuaranteeProductType
    value_source: str | None = None
    user_corrections_applied: dict[str, str | int | bool] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    ai_api_status: AiApiStatus
    ai_api_message: str | None = None
    guarantee: GuaranteeResponse
    guarantee_branch: GuaranteeGroup
    guarantee_message: str
    guarantee_disclaimer: str
    risk_stage: str
    risk_score: int
    deposit_ratio: float
    signal_count: int
    unknown_count: int
    category_scores: dict[str, CategoryScore]
    signals: list[RiskSignal]
    property_summary: PropertySummary
    similar_cases: list[dict[str, Any]]
    easy_explanation: dict[str, Any] | None = None
    checklist: list[dict[str, Any]]
    recommended_action: dict[str, str]
    market_context: list[dict[str, Any]]
    data_sources: list[dict[str, str]]
    generated_at: str
    disclaimer: str


class SimulationSnapshot(BaseModel):
    risk_score: int
    risk_stage: str
    signal_count: int
    property_summary: PropertySummary


class SimulateResponse(BaseModel):
    current: SimulationSnapshot
    changed: SimulationSnapshot
    delta: dict[str, int]
    disclaimer: str
    generated_at: str
