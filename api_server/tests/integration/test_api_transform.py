# api_server/tests/integration/test_api_transform.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection
"""
DI 오버라이드: Depends(get_pipeline_resolver)를 테스트 더블로 교체.
단일 소스(html/tsv): 올바른 Collection 매핑과 서비스 호출 인자 검증, 더미 리턴값이 응답 data에 전달되는지 확인.
전체(all): 두 서비스 모두 호출되고 마지막(tsv) 결과가 응답 data에 담기는지 확인.
잘못된 source: 현재 구현 기준 500 응답 확인.
"""

class DummyResolver:
    """routers.transform 에서 resolver.for_type(FileType)로 서비스 반환을 흉내내는 간단한 대역"""
    def __init__(self, mapping):
        self._mapping = mapping

    def for_type(self, ft: FileType):
        return self._mapping[ft]


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def svc_html():
    m = MagicMock()
    # transform(source, date, collection) → 보통 normalized JSONL 파일명을 반환하게 가정
    m.transform.return_value = "wiki_3_normalized.json"
    return m


@pytest.fixture
def svc_tsv():
    m = MagicMock()
    m.transform.return_value = "qna_3_normalized.json"
    return m


@pytest.fixture(autouse=True)
def override_resolver(svc_html, svc_tsv):
    """Depends(get_pipeline_resolver) DI 오버라이드"""
    resolver = DummyResolver(
        {
            FileType.html: svc_html,
            FileType.tsv:  svc_tsv,
        }
    )
    app.dependency_overrides[get_pipeline_resolver] = lambda: resolver
    yield
    app.dependency_overrides.clear()


def test_transform_single_tsv(client, svc_html, svc_tsv):
    r = client.post("/api/transform", json={"source": "tsv", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["message"].startswith("문서 변환 성공")
    assert body["data"] == {'tsv': 'qna_3_normalized.json'}

    svc_tsv.transform.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)
    svc_html.transform.assert_not_called()


def test_transform_single_html(client, svc_html, svc_tsv):
    r = client.post("/api/transform", json={"source": "html", "date": "4"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # 더미 서비스가 고정값을 반환하도록 했으므로 아래 값으로 검증
    assert body["data"] == {'html': 'wiki_3_normalized.json'}

    svc_html.transform.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.transform.assert_not_called()


def test_transform_all_calls_both_and_returns_last(client, svc_html, svc_tsv):
    """
    source=all 이면 FileType.__members__ 순서(html, tsv)로 두 서비스를 호출.
    구현상 마지막 호출(tsv)의 반환값이 응답 data에 담긴다.
    """
    r = client.post("/api/transform", json={"source": "all", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {'html': 'wiki_3_normalized.json', 'tsv': 'qna_3_normalized.json'}

    svc_html.transform.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.transform.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)


def test_transform_invalid_source_returns_500(client, svc_html, svc_tsv):
    """
    잘못된 source 값은 FileType(...) 캐스팅에서 ValueError -> 422 리턴
    """
    r = client.post("/api/transform", json={"source": "pdf", "date": "3"})
    assert r.status_code == 422

    svc_html.transform.assert_not_called()
    svc_tsv.transform.assert_not_called()
