"""
문서 추출 후 저장하는 API 라우터.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType, ApiResponse
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extract"])

class ExtractRequest(BaseModel):
    """
    문서 추출 요청 바디
    """
    # all | html | tsv
    source: Literal["all", "html", "tsv"] = Field("all", description="default: all (html|tsv)")
    date: str = Field(..., description="날짜(예: '3')")

def _run_extract_one(resolver: PipelineResolver, ft: FileType, date: str) -> Any:
    """파일 타입 1개에 대해 extract 실행."""
    collection = choose_collection(ft)
    svc = resolver.for_type(ft)
    return svc.extract(source=ft.value, date=date, collection=collection)

@router.post(
    "",
    summary="문서 추출 후 저장",
    description=(
        "요청한 소스 유형(html/tsv)에 대해 문서를 추출하고 저장합니다. "
        "`source`가 `all`이면 두 유형을 순차 처리하여 타입별 결과를 반환합니다."
    ),
    operation_id="extractDocuments",
    status_code=200,
    response_model=ApiResponse,
    responses={
        200: {
            "description": "문서 추출 후 저장 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "single_type": {
                            "summary": "단일 타입(html) 처리 예",
                            "value": {
                                "success": True,
                                "message": "문서 추출 후 저장 성공",
                                "data": {
                                    "html": "/data/html/2025-09-22.json"
                                }
                            }
                        },
                        "all_types": {
                            "summary": "전체 타입 처리 예",
                            "value": {
                                "success": True,
                                "message": "문서 추출 후 저장 성공",
                                "data": {
                                    "html": "/data/html/2025-09-22.json",
                                    "tsv": "/data/tsv/2025-09-22.json"
                                }
                            }
                        }
                    }
                }
            },
        },
        400: {"description": "잘못된 요청 값"},
        500: {"description": "서버 내부 오류"},
    },
)
def extract(req: ExtractRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    logger.info(f"ExtractRequest: {req}")
    if req.source == "all":
        # html/tsv 각각 실행하고 타입별 결과를 dict로 반환
        results: Dict[str, Any] = {ft.value: _run_extract_one(resolver, ft, req.date) for ft in FileType}
        return ApiResponse(success=True, message="문서 추출 후 저장 성공", data=results)
    else:
        # 단일 타입
        ft = FileType(req.source)
        result = _run_extract_one(resolver, ft, req.date)
        return ApiResponse(success=True, message="문서 추출 후 저장 성공", data={ft.value: result})
