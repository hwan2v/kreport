# app/api/routers/extract.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.domain.services.extract_service import ExtractService
from api_server.app.api.deps import get_extract_service

router = APIRouter(prefix="/extract", tags=["extract"])

class ExtractRequest(BaseModel):
    source: str = Field(..., description="html or tsv")
    date: str = Field(..., description="날짜")

@router.post("", summary="문서 추출 후 저장")
def extract(req: ExtractRequest, svc: ExtractService = Depends(get_extract_service)):
    print(req)
    result = svc.run(source=req.source, date=req.date)
    print(result)
    return {"success": True, "message": "문서 추출 후 저장 성공", "data": result.model_dump()}
