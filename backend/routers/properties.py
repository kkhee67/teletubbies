from fastapi import APIRouter, HTTPException, Query

from repositories import property_repository
from schemas import PropertySearchResponse


router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("/search", response_model=PropertySearchResponse)
def search_properties(
    q: str = Query(default="", description="주소 일부 또는 구/동 이름"),
) -> dict[str, list[dict]]:
    items = property_repository.search(q)
    return {"items": items[:10]}


@router.get("/{property_id}")
def get_property(property_id: str) -> dict:
    item = property_repository.get(property_id)
    if item is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다.")
    return item
