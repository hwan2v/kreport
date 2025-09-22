from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType


router = APIRouter(prefix="/transform", tags=["transform"])

class TransformRequest(BaseModel):
    source: Literal["all", "html", "tsv"] = Field("all", description="default: all (html|tsv)")
    date: str = Field(..., description="날짜(예: '3')")

def _run_transform_one(resolver: PipelineResolver, ft: FileType, date: str) -> Any:
    """파일 타입 1개에 대해 index 실행."""
    collection = choose_collection(ft)
    svc = resolver.for_type(ft)
    return svc.transform(source=ft.value, date=date, collection=collection)

@router.post("", summary="문서 추출 후 저장")
def transform(req: TransformRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    if req.source == "all":
        # html/tsv 각각 실행하고 타입별 결과를 dict로 반환
        results: Dict[str, Any] = {ft.value: _run_transform_one(resolver, ft, req.date) for ft in FileType}
        return {"success": True, "message": "문서 변환 성공", "data": results}
    else:
        ft = FileType(req.source)
        result = _run_transform_one(resolver, ft, req.date)
        return {"success": True, "message": "문서 변환 성공", "data": {ft.value: result}}
