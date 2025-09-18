# app/api/routers/extract.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.domain.services.search_service import SearchService
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver

router = APIRouter(prefix="/extract", tags=["extract"])

class ExtractRequest(BaseModel):
    source: str = Field(..., description="html or tsv")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 추출 후 저장")
def extract(req: ExtractRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    svc = resolver.for_type(req.source)
    result = svc.run_extract(source=req.source, date=req.date)
    return {"success": True, "message": "문서 추출 후 저장 성공", "data": result}
