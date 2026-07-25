from fastapi import APIRouter, HTTPException

from schemas import AnalyzeRequest, SimulateRequest
from services import analysis_service


router = APIRouter(tags=["analysis"])


@router.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    try:
        return analysis_service.analyze_contract(request)
    except ValueError as exc:
        if str(exc) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate")
def simulate(request: SimulateRequest) -> dict:
    try:
        current = analysis_service.analyze_contract(request.current)
        changed = analysis_service.analyze_contract(request.changed)
    except ValueError as exc:
        if str(exc) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "current": {
            "risk_score": current["risk_score"],
            "risk_stage": current["risk_stage"],
            "signal_count": current["signal_count"],
            "property_summary": current["property_summary"],
        },
        "changed": {
            "risk_score": changed["risk_score"],
            "risk_stage": changed["risk_stage"],
            "signal_count": changed["signal_count"],
            "property_summary": changed["property_summary"],
        },
        "delta": {
            "risk_score": changed["risk_score"] - current["risk_score"],
            "signal_count": changed["signal_count"] - current["signal_count"],
        },
        "disclaimer": "시뮬레이션은 법적 안전을 보장하지 않고 위험신호의 변화를 보여줍니다.",
    }
