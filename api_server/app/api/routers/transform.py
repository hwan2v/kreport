from fastapi import APIRouter, Depends
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from pydantic import BaseModel, Field

router = APIRouter(prefix="/transform", tags=["transform"])#, dependencies=[Depends(require_api_key)])

class TransformRequest(BaseModel):
    source: str = Field(..., description="html or tsv")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 추출 후 저장")
def transform(req: TransformRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    svc = resolver.for_type(req.source)
    result = svc.transform(source=req.source, date=req.date)
    return {"success": True, "message": "문서 변환 성공", "data": result}
