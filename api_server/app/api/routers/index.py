from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any
from api_server.app.api.deps import get_pipeline_resolver, PipelineResolver
from api_server.app.domain.utils import choose_collection
from api_server.app.domain.models import FileType
import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/index", tags=["index"])

class IndexRequest(BaseModel):
    """
    문서 인덱싱 요청 바디
    """
    # all | html | tsv
    source: Literal["all", "html", "tsv"] = Field("all", description="default: all (html|tsv)")
    date: str = Field(..., description="날짜(예: '3')")

class ApiResponse(BaseModel):
    """
    문서 추출 응답
    """
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="결과 메시지")
    # 키: 'html' 또는 'tsv' (source=all인 경우 두 키 모두 존재)
    data: Dict[str, Any] = Field(
        ...,
        description="타입별 결과 딕셔너리. 내부 구조는 작업 타입에 따라 상이"
    )

def _run_index_one(resolver: PipelineResolver, ft: FileType, date: str) -> Any:
    """파일 타입 1개에 대해 index 실행."""
    collection = choose_collection(ft)
    svc = resolver.for_type(ft)
    return svc.index(source=ft.value, date=date, collection=collection)

@router.post(
    "",
    summary="문서 인덱싱",
    description=(
        "요청한 소스 유형(html/tsv)에 대해 문서를 인덱싱합니다. "
        "`source`가 `all`이면 두 유형을 순차 처리하여 타입별 결과를 반환합니다."
    ),
    operation_id="indexDocuments",
    status_code=200,
    response_model=ApiResponse,
    responses={
        200: {
            "description": "문서 인덱싱 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "single_type": {
                            "summary": "단일 타입(html) 처리 예",
                            "value": {
                                "success": True,
                                "message": "문서 인덱싱 성공",
                                "data": {
                                    "html": {
                                        "indexed": 8,
                                        "errors": [],
                                        "index_name": [
                                            "collection-html-3"
                                        ],
                                        "alias_name": "kakaobank"
                                    }
                                }
                            }
                        },
                        "all_types": {
                            "summary": "전체 타입 처리 예",
                            "value": {
                                "success": True,
                                "message": "문서 인덱싱 성공",
                                "data": {
                                    "html": {
                                        "indexed": 8,
                                        "errors": [],
                                        "index_name": [
                                            "collection-html-3"
                                        ],
                                        "alias_name": "kakaobank"
                                    },
                                    "tsv": {
                                        "indexed": 100,
                                        "errors": [],
                                        "index_name": [
                                            "collection-html-3",
                                            "collection-tsv-3"
                                        ],
                                        "alias_name": "kakaobank"
                                    }
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
def index(req: IndexRequest, resolver: PipelineResolver = Depends(get_pipeline_resolver)):
    logger.info(f"IndexRequest: {req}")
    if req.source == "all":
        # html/tsv 각각 실행하고 타입별 결과를 dict로 반환
        results: Dict[str, Any] = {ft.value: _run_index_one(resolver, ft, req.date) for ft in FileType}
        return ApiResponse(success=True, message="문서 인덱싱 성공", data=results)
    else:
        ft = FileType(req.source)
        result = _run_index_one(resolver, ft, req.date)
        return ApiResponse(success=True, message="문서 인덱싱 성공", data={ft.value: result})
