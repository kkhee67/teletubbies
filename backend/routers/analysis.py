from fastapi import APIRouter

from errors import ApiError
from schemas import AnalyzeRequest, AnalyzeResponse, SimulateRequest, SimulateResponse
from services import analysis_service


router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> dict:
    try:
        return analysis_service.analyze_contract(request)
    except ValueError as exc:
        raise api_error_from_value_error(exc) from exc


@router.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> dict:
    try:
        return analysis_service.simulate_contract(request)
    except ValueError as exc:
        raise api_error_from_value_error(exc) from exc


def api_error_from_value_error(exc: ValueError) -> ApiError:
    if str(exc) == "PROPERTY_NOT_FOUND":
        return ApiError(
            status_code=404,
            detail="매물을 찾을 수 없습니다.",
            code="PROPERTY_NOT_FOUND",
        )
    return ApiError(status_code=400, detail=str(exc), code="INVALID_REQUEST")
