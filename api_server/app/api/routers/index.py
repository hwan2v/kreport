from fastapi import APIRouter, Depends
from api_server.app.security.guards import require_api_key
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from pydantic import BaseModel, Field
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType

from api_server.app.domain.services.search_service import SearchService

router = APIRouter(prefix="/index", tags=["index"])# dependencies=[Depends(require_api_key)])

class IndexRequest(BaseModel):
    source: str = Field("all", description="html or tsv")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 인덱싱")
def index(req: IndexRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    if req.source == "all":
        for filetype in FileType.__members__.keys():
            ft = FileType(filetype)
            collection = choose_collection(ft)
            svc = resolver.for_type(ft)
            result = svc.index(source=ft.value, date=req.date, collection=collection)
    else:
        ft = FileType(req.source)
        collection = choose_collection(ft)
        svc = resolver.for_type(ft)
        result = svc.index(source=ft.value, date=req.date, collection=collection)
    return {"success": True, "message": "문서 인덱싱 성공", "data": result}
