from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from api_server.app.platform.config import settings
from api_server.app.security.guards import require_api_key

router = APIRouter(prefix="/search", tags=["search"])# dependencies=[Depends(require_api_key)])


class SearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리")
    size: int = Field(..., description="검색 결과 개수")

@router.post("", summary="문서 추출 후 저장")
def search(req: SearchRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    svc = resolver.for_type('tsv')
    result = svc.search(query=req.query, size=req.size)
    return {"success": True, "message": "검색 성공", "data": result}
