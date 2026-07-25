from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    property_id: str = Field(min_length=2, max_length=20)
    address_query: Optional[str] = Field(default=None, max_length=200)
    planned_deposit: int = Field(gt=0)
    monthly_rent: int = Field(default=0, ge=0)
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
    guarantee_status: str


class PropertySearchResponse(BaseModel):
    items: list[PropertySearchItem]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
