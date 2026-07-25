from __future__ import annotations

from copy import deepcopy
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contract_workflow import (
    build_contract_response,
    contract_options,
)
from easy_explanation import enrich_similar_case
from guarantee_products import (
    JEONSE_RETURN,
    PRODUCT_LABELS,
    RENTAL_DEPOSIT,
    canonical_product_type,
)
from mock_properties import MockPropertyRepository
from product_context import ProductContextRepository
from similar_cases import SimilarCaseSearchEngine


RESPONSE_DISCLAIMER = (
    "유사도는 상담사례의 조건이 비슷한 정도이며 위험 확률이나 사고 확률이 아닙니다. "
    "이 결과는 계약 전 확인을 돕는 참고정보로서 법률 판단이나 동일한 피해 발생을 예측하지 않습니다."
)


class AnalysisItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = None
    title: str | None = None
    severity: str | None = None


class SourceAttributionInput(BaseModel):
    source_type: Literal[
        "official", "user_confirmed", "mock", "unknown", "unavailable"
    ]
    source_name: str = Field(min_length=1, max_length=200)
    reference_date: date | None = None


class HousingTypeFactInput(BaseModel):
    value: str = Field(min_length=1, max_length=100)
    source: SourceAttributionInput


class ReferenceValueFactInput(BaseModel):
    amount: int = Field(gt=0)
    value_type: str = Field(default="reference_value", max_length=100)
    source: SourceAttributionInput


class RightFactInput(BaseModel):
    status: Literal["exists", "none", "unknown"]
    amount: int | None = Field(default=None, ge=0)
    source: SourceAttributionInput


class OfficetelUseFactInput(BaseModel):
    status: Literal["residential", "business", "unknown"]
    value: str | None = Field(default=None, max_length=100)
    source: SourceAttributionInput


class SeniorTenantDepositsFactInput(BaseModel):
    status: Literal["confirmed", "unknown"]
    amount: int | None = Field(default=None, ge=0)
    source: SourceAttributionInput


class PropertyFactsInput(BaseModel):
    housing_type: HousingTypeFactInput | None = None
    reference_value: ReferenceValueFactInput | None = None
    mortgage: RightFactInput | None = None
    seizure: RightFactInput | None = None
    joint_collateral: RightFactInput | None = None
    officetel_use: OfficetelUseFactInput | None = None
    senior_tenant_deposits: SeniorTenantDepositsFactInput | None = None


class GuaranteeFactInput(BaseModel):
    status: Literal[
        "estimated_eligible",
        "officially_eligible",
        "applied",
        "enrolled",
        "ineligible",
        "unknown",
    ]
    source: SourceAttributionInput


class ContractAnalysisRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "address": "부산광역시 수영구 광안동 123-45",
                "planned_deposit": 200000000,
                "situation_text": "집주인이 잔금일에 근저당을 말소한다고 했습니다.",
                "guarantee_product_type": "jeonse_return",
                "demo_mode": True,
                "top_k": 3,
            }
        }
    )

    address: str = Field(min_length=2, max_length=200)
    planned_deposit: int = Field(gt=0)
    situation_text: str | None = Field(default=None, max_length=2_000)
    guarantee_product_type: str
    property_facts: PropertyFactsInput | None = None
    guarantee_fact: GuaranteeFactInput | None = None
    demo_mode: bool = False
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("주소를 2자 이상 입력해야 합니다.")
        return normalized

    @field_validator("situation_text")
    @classmethod
    def normalize_situation_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("guarantee_product_type")
    @classmethod
    def validate_contract_product_type(cls, value: str) -> str:
        product_type = canonical_product_type(value)
        if product_type not in {JEONSE_RETURN, RENTAL_DEPOSIT}:
            raise ValueError(
                "guarantee_product_type은 jeonse_return 또는 rental_deposit이어야 합니다."
            )
        return product_type


class AnalyzeRequest(BaseModel):
    property_id: str = Field(min_length=1, max_length=100)
    deposit: int = Field(gt=0)
    guarantee_status: Literal[
        "estimated_eligible",
        "officially_eligible",
        "applied",
        "enrolled",
        "ineligible",
        "unknown",
    ] | None = None
    user_text: str | None = Field(default=None, max_length=2_000)
    user_confirmations: PropertyFactsInput | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class SimulationChanges(BaseModel):
    deposit: int | None = Field(default=None, gt=0)
    mortgage_status: Literal["exists", "none", "unknown"] | None = None
    joint_collateral_status: Literal["exists", "none", "unknown"] | None = None
    guarantee_status: Literal[
        "estimated_eligible",
        "officially_eligible",
        "applied",
        "enrolled",
        "ineligible",
        "unknown",
    ] | None = None


class SimulationRequest(BaseModel):
    property_id: str = Field(min_length=1, max_length=100)
    deposit: int = Field(gt=0)
    changes: SimulationChanges
    user_text: str | None = Field(default=None, max_length=2_000)
    top_k: int = Field(default=3, ge=1, le=10)


class PropertyData(BaseModel):
    # 상세주소나 사용자 연락처 같은 불필요한 추가 필드는 검색 입력에서 제외한다.
    model_config = ConfigDict(extra="ignore")

    property_id: str | None = None
    region_sido: str | None = None
    region_sigungu: str | None = None
    housing_type: str | None = None
    deposit: int | None = Field(default=None, ge=0)
    planned_deposit: int | None = Field(default=None, ge=0)
    deposit_range: str | None = None
    senior_rights: str | None = None
    mortgage_status: str | None = None
    guarantee_status: str | None = None
    guarantee_product_type: str
    guarantee: dict[str, Any] | None = None

    @field_validator("guarantee_product_type")
    @classmethod
    def validate_product_type(cls, value: str) -> str:
        product_type = canonical_product_type(value)
        if product_type not in {JEONSE_RETURN, RENTAL_DEPOSIT}:
            raise ValueError(
                "guarantee_product_type은 jeonse_return 또는 rental_deposit이어야 합니다."
            )
        return product_type


class AnalysisData(BaseModel):
    model_config = ConfigDict(extra="allow")

    confirmed_risks: list[AnalysisItem | str] = Field(default_factory=list)
    required_checks: list[AnalysisItem | str] = Field(default_factory=list)


class SimilarCasesRequest(BaseModel):
    property_data: PropertyData
    analysis: AnalysisData = Field(default_factory=AnalysisData)
    user_text: str | None = Field(default=None, max_length=2_000)
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("user_text")
    @classmethod
    def normalize_user_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_search_context(self):
        property_values = self.property_data.model_dump(
            exclude_none=True, exclude_defaults=True
        )
        has_analysis = bool(
            self.analysis.confirmed_risks or self.analysis.required_checks
        )
        if not property_values and not has_analysis and not self.user_text:
            raise ValueError("매물정보, 분석결과, 사용자 설명 중 하나는 필요합니다.")
        return self


class SimilarCaseSourcePublic(BaseModel):
    source_type: str
    source_name: str
    is_synthetic: bool


class SimilarCasePublic(BaseModel):
    case_id: str
    case_product_type: str
    case_product_label: str
    similarity: float
    similarity_label: str
    matched_factors: list[str]
    confirmed_risk_tags: list[str]
    required_check_tags: list[str]
    dispute_type: str
    progress_stage: str
    easy_explanation: str
    actions: list[str]
    explanation_source: str
    safety_passed: bool
    source: SimilarCaseSourcePublic
    disclaimer: str


class FieldSourcePublic(BaseModel):
    source_type: str
    source_name: str
    reference_date: str | None
    is_verified: bool


class ContractPropertyPublic(BaseModel):
    property_id: str
    display_address: str
    region_sido: str | None
    region_sigungu: str | None
    is_mock: bool
    planned_deposit: int
    planned_deposit_display: str
    privacy_notice: str


class PropertyFactCardPublic(BaseModel):
    key: str
    label: str
    value: Any
    display_value: str
    state: Literal["info", "confirmed", "warning", "check_required"]
    description: str
    details: dict[str, Any]
    source: FieldSourcePublic


class PropertySnapshotPublic(BaseModel):
    cards: list[PropertyFactCardPublic]
    notice: str


class GuaranteePublic(BaseModel):
    product_type: str
    product_label: str
    status: str
    display_text: str
    headline: str
    group: str
    group_order: int
    group_display_text: str
    summary: str
    warning: str
    is_enrolled: bool
    actions: list[str]
    source: FieldSourcePublic


class ContractAnalysisItemPublic(BaseModel):
    code: str
    title: str
    severity: str
    fact_key: str
    source_type: str
    source_name: str
    description: str


class ContractRiskAnalysisPublic(BaseModel):
    risk_stage: str
    risk_stage_notice: str
    confirmed_risk_count: int
    required_check_count: int
    analysis_confidence: int
    analysis_confidence_notice: str
    deposit_to_reference_ratio_pct: float | None
    deposit_ratio_rule_notice: str | None
    confirmed_risks: list[ContractAnalysisItemPublic]
    required_checks: list[ContractAnalysisItemPublic]


class ChecklistItemPublic(BaseModel):
    id: str
    title: str
    reason: str
    priority: str
    completed: bool


class DataUsageSourcePublic(BaseModel):
    source_id: str
    source_label: str
    record_count: int
    role: str
    used_for: str
    applied_to_request: bool
    product_mapping_basis: str


class DataUsagePublic(BaseModel):
    total_source_count: int
    applied_source_count: int
    selected_product_type: str
    sources: list[DataUsageSourcePublic]
    notice: str


class LocationContextPublic(BaseModel):
    included_in_risk_score: bool
    items: list[dict[str, Any]]
    source_type: str = "unknown"
    source_name: str
    reference_date: str | None
    notice: str


class ContractResponseMeta(BaseModel):
    schema_version: str
    analysis_version: str
    selected_product_type: str
    selected_product_label: str
    data_source_count: int
    is_accident_probability: bool
    ai_search_status: str
    warnings: list[str]
    notice: str


class ResponseMeta(BaseModel):
    result_count: int
    search_method: str = "tfidf_structured_rerank"
    is_accident_probability: bool = False
    similarity_notice: str = (
        "유사도는 상담사례의 조건이 비슷한 정도이며 위험 확률이나 사고 확률이 아닙니다."
    )
    selected_product_type: str
    selected_product_label: str
    product_separation_applied: bool
    data_source_count: int


class ProductDataSourcePublic(BaseModel):
    source_id: str
    source_label: str
    product_scope: str
    record_count: int
    matching_housing_type_count: int | None
    matching_region_sido_count: int | None
    metrics: dict[str, Any]
    reference_period: dict[str, str | None] = Field(
        default_factory=lambda: {"from": None, "to": None}
    )
    reference_date: str | None = None
    future_date_count: int = 0
    data_quality_notes: list[str] = Field(default_factory=list)


class ProductContextPublic(BaseModel):
    selected_product_type: str
    selected_product_label: str
    product_separation_applied: bool
    source_count: int
    sources: list[ProductDataSourcePublic]
    notice: str


class SimilarCasesResponse(BaseModel):
    status: Literal["ok", "fallback", "unavailable"]
    similar_cases: list[SimilarCasePublic]
    product_context: ProductContextPublic
    meta: ResponseMeta
    disclaimer: str = RESPONSE_DISCLAIMER


class ContractAnalysisResponse(BaseModel):
    property: ContractPropertyPublic
    property_snapshot: PropertySnapshotPublic
    guarantee: GuaranteePublic
    analysis: ContractRiskAnalysisPublic
    similar_cases: list[SimilarCasePublic]
    checklist: list[ChecklistItemPublic]
    historical_context: ProductContextPublic
    data_usage: DataUsagePublic
    location_context: LocationContextPublic
    meta: ContractResponseMeta


class ContractOptionsResponse(BaseModel):
    guarantee_products: list[dict[str, Any]]
    guarantee_statuses: list[dict[str, Any]]
    guarantee_groups: list[dict[str, Any]]
    source_types: list[dict[str, Any]]


class PropertySearchItemPublic(BaseModel):
    property_id: str
    display_address: str
    is_mock: bool
    guarantee_product_type: str


class PropertyLookupResponse(BaseModel):
    property: dict[str, Any]
    property_facts: dict[str, Any]
    guarantee_fact: dict[str, Any]
    location_context: LocationContextPublic


class SimulationSnapshotPublic(BaseModel):
    guarantee: GuaranteePublic
    analysis: ContractRiskAnalysisPublic


class SimulationResponse(BaseModel):
    property: ContractPropertyPublic
    before: SimulationSnapshotPublic
    after: SimulationSnapshotPublic
    comparison: dict[str, Any]
    is_simulation: bool
    notice: str


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    model_loaded: bool
    case_count: int
    product_context_loaded: bool
    data_source_count: int
    mock_property_count: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.search_engine = SimilarCaseSearchEngine()
    app.state.product_context = ProductContextRepository()
    app.state.mock_properties = MockPropertyRepository()
    yield
    app.state.search_engine = None
    app.state.product_context = None
    app.state.mock_properties = None


app = FastAPI(
    title="안심계약 레이더 AI API",
    description=(
        "백엔드 내부 호출용 AI 서비스입니다. 운영 공개 계약은 상태 확인과 "
        "상품별 유사사례 검색으로 제한합니다."
    ),
    version="3.1.0",
    lifespan=lifespan,
)


def get_search_engine(request: Request) -> SimilarCaseSearchEngine:
    engine = getattr(request.app.state, "search_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="검색엔진이 준비되지 않았습니다.")
    return engine


def get_mock_properties(request: Request) -> MockPropertyRepository:
    repository = getattr(request.app.state, "mock_properties", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="모의 매물 데이터가 준비되지 않았습니다.")
    return repository


def public_case(result: dict) -> SimilarCasePublic:
    public_fields = SimilarCasePublic.model_fields.keys()
    return SimilarCasePublic(**{key: result[key] for key in public_fields})


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    engine = getattr(request.app.state, "search_engine", None)
    product_context = getattr(request.app.state, "product_context", None)
    mock_properties = getattr(request.app.state, "mock_properties", None)
    return HealthResponse(
        status=(
            "ok"
            if engine is not None
            and product_context is not None
            and mock_properties is not None
            else "unavailable"
        ),
        model_loaded=engine is not None,
        case_count=len(engine.cases) if engine is not None else 0,
        product_context_loaded=product_context is not None,
        data_source_count=(
            product_context.data_source_count if product_context is not None else 0
        ),
        mock_property_count=(mock_properties.count if mock_properties else 0),
    )


def get_mock_or_404(
    repository: MockPropertyRepository, property_id: str
) -> dict[str, Any]:
    try:
        return repository.get(property_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="선택한 모의 매물을 찾을 수 없습니다."
        ) from exc


def mock_property_identity(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "property_id": item["property_id"],
        "display_address": item["display_address"],
        "region_sido": item.get("region_sido"),
        "region_sigungu": item.get("region_sigungu"),
        "is_mock": True,
    }


def build_mock_analysis(
    *,
    item: dict[str, Any],
    deposit: int,
    user_text: str | None,
    top_k: int,
    engine: SimilarCaseSearchEngine,
    context_repository: ProductContextRepository,
    property_facts: dict[str, Any] | None = None,
    guarantee_fact: dict[str, Any] | None = None,
) -> ContractAnalysisResponse:
    result = build_contract_response(
        address=item["search_address"],
        planned_deposit=deposit,
        situation_text=user_text,
        product_type=item["guarantee_product_type"],
        property_facts=property_facts or item["property_facts"],
        guarantee_fact=guarantee_fact or item["guarantee_fact"],
        demo_mode=True,
        top_k=top_k,
        search_engine=engine,
        context_repository=context_repository,
        property_identity=mock_property_identity(item),
        location_context=item["location_context"],
    )
    return ContractAnalysisResponse(**result)


@app.get(
    "/properties/search",
    response_model=list[PropertySearchItemPublic],
    include_in_schema=False,
)
def search_mock_properties(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
) -> list[PropertySearchItemPublic]:
    repository = get_mock_properties(request)
    return [PropertySearchItemPublic(**item) for item in repository.search(q)]


@app.get(
    "/properties/{property_id}",
    response_model=PropertyLookupResponse,
    include_in_schema=False,
)
def get_mock_property(
    property_id: str, request: Request
) -> PropertyLookupResponse:
    item = get_mock_or_404(get_mock_properties(request), property_id)
    return PropertyLookupResponse(
        property={
            **mock_property_identity(item),
            "guarantee_product_type": item["guarantee_product_type"],
        },
        property_facts=item["property_facts"],
        guarantee_fact=item["guarantee_fact"],
        location_context=LocationContextPublic(**item["location_context"]),
    )


@app.post(
    "/analyze", response_model=ContractAnalysisResponse, include_in_schema=False
)
def analyze_mock_property(
    payload: AnalyzeRequest, request: Request
) -> ContractAnalysisResponse:
    repository = get_mock_properties(request)
    item = get_mock_or_404(repository, payload.property_id)
    facts = deepcopy(item["property_facts"])
    if payload.user_confirmations:
        facts.update(
            payload.user_confirmations.model_dump(mode="json", exclude_none=True)
        )
    guarantee_fact = deepcopy(item["guarantee_fact"])
    if payload.guarantee_status:
        guarantee_fact = {
            "status": payload.guarantee_status,
            "source": {
                "source_type": "user_confirmed",
                "source_name": "사용자 확인",
                "reference_date": date.today().isoformat(),
            },
        }
    context_repository = getattr(request.app.state, "product_context", None)
    if context_repository is None:
        raise HTTPException(status_code=503, detail="상품별 데이터가 준비되지 않았습니다.")
    return build_mock_analysis(
        item=item,
        deposit=payload.deposit,
        user_text=payload.user_text,
        top_k=payload.top_k,
        engine=get_search_engine(request),
        context_repository=context_repository,
        property_facts=facts,
        guarantee_fact=guarantee_fact,
    )


@app.post(
    "/simulate", response_model=SimulationResponse, include_in_schema=False
)
def simulate_contract(
    payload: SimulationRequest, request: Request
) -> SimulationResponse:
    item = get_mock_or_404(get_mock_properties(request), payload.property_id)
    context_repository = getattr(request.app.state, "product_context", None)
    if context_repository is None:
        raise HTTPException(status_code=503, detail="상품별 데이터가 준비되지 않았습니다.")
    engine = get_search_engine(request)
    before = build_mock_analysis(
        item=item,
        deposit=payload.deposit,
        user_text=payload.user_text,
        top_k=payload.top_k,
        engine=engine,
        context_repository=context_repository,
    )

    simulation_source = {
        "source_type": "simulation",
        "source_name": "사용자 조건 변경 시뮬레이션",
        "reference_date": date.today().isoformat(),
    }
    after_facts = deepcopy(item["property_facts"])
    if payload.changes.mortgage_status:
        after_facts["mortgage"] = {
            "status": payload.changes.mortgage_status,
            "amount": None,
            "source": simulation_source,
        }
    if payload.changes.joint_collateral_status:
        after_facts["joint_collateral"] = {
            "status": payload.changes.joint_collateral_status,
            "amount": None,
            "source": simulation_source,
        }
    after_guarantee = deepcopy(item["guarantee_fact"])
    if payload.changes.guarantee_status:
        after_guarantee = {
            "status": payload.changes.guarantee_status,
            "source": simulation_source,
        }
    after_deposit = payload.changes.deposit or payload.deposit
    after = build_mock_analysis(
        item=item,
        deposit=after_deposit,
        user_text=payload.user_text,
        top_k=payload.top_k,
        engine=engine,
        context_repository=context_repository,
        property_facts=after_facts,
        guarantee_fact=after_guarantee,
    )

    before_analysis = before.analysis
    after_analysis = after.analysis
    comparison = {
        "risk_stage": {
            "before": before_analysis.risk_stage,
            "after": after_analysis.risk_stage,
            "changed": before_analysis.risk_stage != after_analysis.risk_stage,
        },
        "confirmed_risk_count": {
            "before": before_analysis.confirmed_risk_count,
            "after": after_analysis.confirmed_risk_count,
            "delta": (
                after_analysis.confirmed_risk_count
                - before_analysis.confirmed_risk_count
            ),
        },
        "required_check_count": {
            "before": before_analysis.required_check_count,
            "after": after_analysis.required_check_count,
            "delta": (
                after_analysis.required_check_count
                - before_analysis.required_check_count
            ),
        },
        "analysis_confidence": {
            "before": before_analysis.analysis_confidence,
            "after": after_analysis.analysis_confidence,
            "delta": (
                after_analysis.analysis_confidence
                - before_analysis.analysis_confidence
            ),
        },
    }
    return SimulationResponse(
        property=after.property,
        before=SimulationSnapshotPublic(
            guarantee=before.guarantee,
            analysis=before.analysis,
        ),
        after=SimulationSnapshotPublic(
            guarantee=after.guarantee,
            analysis=after.analysis,
        ),
        comparison=comparison,
        is_simulation=True,
        notice=(
            "조건 변경 결과는 가정 비교입니다. 화면에서 근저당 말소나 보증 상태를 바꿔도 "
            "실제 완료로 확인된 것이 아니며 공식 서류를 다시 확인해야 합니다."
        ),
    )


@app.get(
    "/api/contract-options",
    response_model=ContractOptionsResponse,
    include_in_schema=False,
)
def get_contract_options() -> ContractOptionsResponse:
    return ContractOptionsResponse(**contract_options())


@app.post(
    "/api/contract-analysis",
    response_model=ContractAnalysisResponse,
    include_in_schema=False,
)
def analyze_contract(
    payload: ContractAnalysisRequest, request: Request
) -> ContractAnalysisResponse:
    engine = get_search_engine(request)
    context_repository = getattr(request.app.state, "product_context", None)
    if context_repository is None:
        raise HTTPException(status_code=503, detail="상품별 데이터가 준비되지 않았습니다.")

    property_facts = (
        payload.property_facts.model_dump(mode="json", exclude_none=True)
        if payload.property_facts
        else None
    )
    guarantee_fact = (
        payload.guarantee_fact.model_dump(mode="json", exclude_none=True)
        if payload.guarantee_fact
        else None
    )
    try:
        result = build_contract_response(
            address=payload.address,
            planned_deposit=payload.planned_deposit,
            situation_text=payload.situation_text,
            product_type=payload.guarantee_product_type,
            property_facts=property_facts,
            guarantee_fact=guarantee_fact,
            demo_mode=payload.demo_mode,
            top_k=payload.top_k,
            search_engine=engine,
            context_repository=context_repository,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ContractAnalysisResponse(**result)


@app.post("/api/similar-cases", response_model=SimilarCasesResponse)
def search_similar_cases(
    payload: SimilarCasesRequest, request: Request
) -> SimilarCasesResponse:
    engine = get_search_engine(request)
    context_repository = getattr(request.app.state, "product_context", None)
    if context_repository is None:
        raise HTTPException(status_code=503, detail="상품별 데이터가 준비되지 않았습니다.")
    property_data = payload.property_data.model_dump(exclude_none=True)
    selected_product_type = property_data["guarantee_product_type"]
    product_context = context_repository.get_context(
        selected_product_type,
        payload.property_data.housing_type,
        payload.property_data.region_sido,
    )
    status: Literal["ok", "fallback", "unavailable"] = "ok"
    try:
        raw_results = engine.search(
            property_data,
            payload.analysis.model_dump(exclude_none=True),
            payload.user_text,
            payload.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raw_results = []
        status = "unavailable"

    results = []
    for raw_result in raw_results:
        enriched = enrich_similar_case(raw_result)
        if enriched.get("explanation_source") == "template_fallback":
            status = "fallback"
        if enriched.get("safety_passed") is not True:
            if status != "unavailable":
                status = "fallback"
            continue
        results.append(public_case(enriched))

    return SimilarCasesResponse(
        status=status,
        similar_cases=results,
        product_context=ProductContextPublic(**product_context),
        meta=ResponseMeta(
            result_count=len(results),
            selected_product_type=product_context["selected_product_type"],
            selected_product_label=product_context["selected_product_label"],
            product_separation_applied=product_context[
                "product_separation_applied"
            ],
            data_source_count=context_repository.data_source_count,
        ),
    )
