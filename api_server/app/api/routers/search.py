from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.api.deps import get_search_service, SearchService
from api_server.app.platform.config import settings
from api_server.app.security.guards import require_api_key
from typing import Optional

router = APIRouter(prefix="/search", tags=["search"])# dependencies=[Depends(require_api_key)])


class SearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리")
    size: int = Field(3, description="검색 결과 개수")
    explain: bool = Field(False, description="검색 결과 설명 포함 여부")

@router.post("", summary="문서 추출 후 저장")
def search(req: SearchRequest, svc: SearchService = Depends(get_search_service)):
    print(req)
    result = svc.search(query=req.query, size=req.size, explain=req.explain)
    return {"success": True, "message": "검색 성공", "data": result}
