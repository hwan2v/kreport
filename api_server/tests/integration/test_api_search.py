# api_server/tests/integration/test_api_search.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_search_service
"""
DI 오버라이드: Depends(get_search_service)를 목 객체로 교체해 라우터+의존성 레벨의 통합 테스트.
기본값 사용: size=3, explain=False가 적용되어 호출되는지 확인.
파라미터 오버라이드: 명시한 size, explain이 그대로 서비스에 전달되는지 확인.
오류 전파: 서비스에서 예외 발생 시 현재 구현상 500으로 전파됨을 검증.
(원하면 나중에 예외를 캐치해 4xx/5xx를 명시적으로 매핑하는 에러 핸들러 추가도 고려 가능해요.)
"""

@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_search_service():
    svc = MagicMock()
    # 기본 리턴 형태를 OpenSearch 유사 형태로 세팅
    svc.search.return_value = {
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [{"_id": "1", "_score": 10.1, "_source": {"title": "카카오뱅크", "body": "본문"}}],
        }
    }
    return svc


@pytest.fixture(autouse=True)
def override_dependency(mock_search_service):
    """
    라우터의 Depends(get_search_service)를 테스트 더블로 교체
    """
    app.dependency_overrides[get_search_service] = lambda: mock_search_service
    yield
    app.dependency_overrides.clear()


def test_search_defaults(client, mock_search_service):
    """
    기본 파라미터(size=3, explain=False)가 적용되어 서비스가 호출되는지 검증
    """
    payload = {"query": "카카오뱅크"}  # size/explain 생략 → 기본값 사용
    resp = client.post("/api/search", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"].startswith("검색 성공")
    assert "hits" in body["data"]
    # 서비스 호출 파라미터 확인
    mock_search_service.search.assert_called_once_with(query="카카오뱅크", size=3, explain=False)


def test_search_with_params(client, mock_search_service):
    """
    size, explain 파라미터를 오버라이드 했을 때 서비스가 같은 값으로 호출되는지
    """
    payload = {"query": "삼성전자", "size": 5, "explain": True}
    # 서비스 리턴값도 살짝 바꿔보자
    mock_search_service.search.return_value = {
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [
                {"_id": "a", "_score": 12.3, "_source": {"title": "삼성전자", "body": "A"}},
                {"_id": "b", "_score": 9.9, "_source": {"title": "반도체", "body": "B"}},
            ],
        }
    }

    resp = client.post("/api/search", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["hits"]["total"]["value"] == 2
    assert len(body["data"]["hits"]["hits"]) == 2

    mock_search_service.search.assert_called_once_with(query="삼성전자", size=5, explain=True)


def test_search_propagates_error_as_500(client, mock_search_service):
    """
    서비스에서 예외가 발생하면(현재 라우터에 에러 핸들링 없음) 500이 내려오는지 확인
    """
    mock_search_service.search.side_effect = RuntimeError("opensearch down")

    resp = client.post("/api/search", json={"query": "네이버"})
    assert resp.status_code == 500
