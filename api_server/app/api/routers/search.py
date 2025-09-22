from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api_server.app.api.deps import get_search_service, SearchService
from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리")
    size: int = Field(3, description="검색 결과 개수")
    explain: bool = Field(False, description="검색 결과 설명 포함 여부")

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

@router.post(
    "",
    summary="문서 검색",
    description=(
        "쿼리로 문서를 검색합니다. `size`로 반환 개수를 제한하고, "
        "`explain=true`로 설정하면 각 결과에 점수 산출 근거를 포함합니다."
    ),
    operation_id="searchDocuments",
    status_code=200,
    response_model=ApiResponse,
    responses={
        200: {
            "description": "검색 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "basic": {
                            "summary": "기본 검색 예시",
                            "value": {
                                "success": True,
                                "message": "검색 성공",
                                "data": {
                                    "total": 134,
                                    "took_ms": 42,
                                    "items": [
                                        {
                                            "id": "doc_123",
                                            "score": 12.34,
                                            "title": "FastAPI로 만드는 검색 API",
                                            
                                        },
                                        {
                                            "id": "doc_122",
                                            "score": 11.87,
                                            "question": "OpenSearch 튜닝 가이드",
                                        },
                                        {
                                            "id": "doc_121",
                                            "score": 10.01,
                                            "title": "색인 전략과 샤드 설계",
                                        }
                                    ]
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
def search(req: SearchRequest, svc: SearchService = Depends(get_search_service)):
    logger.info(f"SearchRequest: {req}")
    result = svc.search(query=req.query, size=req.size, explain=req.explain)
    return ApiResponse(success=True, message="검색 성공", data=result)
