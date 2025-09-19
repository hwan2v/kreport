from fastapi import APIRouter, Depends
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from pydantic import BaseModel, Field
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType

router = APIRouter(prefix="/transform", tags=["transform"])#, dependencies=[Depends(require_api_key)])

class TransformRequest(BaseModel):
    source: str = Field("all", description="default: all, (html or tsv)")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 추출 후 저장")
def transform(req: TransformRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    if req.source == "all":
        for filetype in FileType.__members__.keys():
            ft = FileType(filetype)
            collection = choose_collection(ft)
            svc = resolver.for_type(ft)
            result = svc.transform(source=ft.value, date=req.date, collection=collection)
    else:
        ft = FileType(req.source)
        collection = choose_collection(ft)
        svc = resolver.for_type(ft)
        result = svc.transform(source=ft.value, date=req.date, collection=collection)
    return {"success": True, "message": "문서 변환 성공", "data": result}
