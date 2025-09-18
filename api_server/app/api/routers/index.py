from fastapi import APIRouter, Depends
from api_server.app.security.guards import require_api_key
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from pydantic import BaseModel, Field

from api_server.app.domain.services.search_service import SearchService

router = APIRouter(prefix="/index", tags=["index"])# dependencies=[Depends(require_api_key)])

class IndexRequest(BaseModel):
    source: str = Field(..., description="html or tsv")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 인덱싱")
def index(req: IndexRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    svc = resolver.for_type(req.source)
    result = svc.run_index(source=req.source, date=req.date)
    return {"success": True, "message": "문서 인덱싱 성공"}
