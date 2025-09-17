# app/api/routers/extract.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.domain.services.extract_service import ExtractService
from app.api.deps import get_extract_service

router = APIRouter(prefix="/extract", tags=["extract"])

class ExtractRequest(BaseModel):
    source: str = Field(..., description="URL 또는 file:// 경로")
    collection: str = Field(..., description="컬렉션 이름")

@router.post("", summary="문서 추출 후 색인")
def extract(req: ExtractRequest, svc: ExtractService = Depends(get_extract_service)):
    result = svc.run(source=req.source, collection=req.collection)
    return result.model_dump()
