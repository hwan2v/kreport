from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType

router = APIRouter(prefix="/extract", tags=["extract"])

class ExtractRequest(BaseModel):
    source: str = Field("all", description="default: all, (html or tsv)")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 추출 후 저장")
def extract(req: ExtractRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    if req.source == "all":
        for filetype in FileType.__members__.keys():
            ft = FileType(filetype)
            collection = choose_collection(ft)
            svc = resolver.for_type(ft)
            result = svc.extract(source=ft.value, date=req.date, collection=collection)
    else:
        ft = FileType(req.source)
        collection = choose_collection(ft)
        svc = resolver.for_type(ft)
        result = svc.extract(source=ft.value, date=req.date, collection=collection)
    return {"success": True, "message": "문서 추출 후 저장 성공", "data": result}
