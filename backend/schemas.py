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
