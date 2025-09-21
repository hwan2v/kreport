# api_server/tests/integration/test_api_index.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection
"""
DI 오버라이드: Depends(get_pipeline_resolver)를 테스트용 DummyResolver로 교체.
단일 소스(html/tsv): 올바른 Collection 매핑과 서비스 호출 파라미터, 응답 구조 검증.
전체(all): 두 서비스 모두 호출되고 마지막(tsv) 결과가 응답 data에 담기는 동작 확인.
잘못된 source: 현재 구현 기준 500 응답 확인(후속 개선 시 400으로 바꾸는 것도 고려해볼 수 있음).
"""

class DummyResolver:
    """routers.index 에서 resolver.for_type(FileType)로 서비스 반환을 흉내내는 간단한 대역"""
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
    # index(source, date, collection) → 인덱싱 결과 dict를 반환하도록 설정
    m.index.return_value = {
        "indexed": 5,
        "errors": [],
        "index_name": ["myidx-html-3"],
        "alias_name": "myalias",
    }
    return m


@pytest.fixture
def svc_tsv():
    m = MagicMock()
    m.index.return_value = {
        "indexed": 7,
        "errors": [],
        "index_name": ["myidx-tsv-3"],
        "alias_name": "myalias",
    }
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


def test_index_single_tsv(client, svc_html, svc_tsv):
    r = client.post("/api/index", json={"source": "tsv", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["message"].startswith("문서 인덱싱")
    assert body["data"]["indexed"] == 7
    assert body["data"]["index_name"] == ["myidx-tsv-3"]
    assert body["data"]["alias_name"] == "myalias"

    svc_tsv.index.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)
    svc_html.index.assert_not_called()


def test_index_single_html(client, svc_html, svc_tsv):
    r = client.post("/api/index", json={"source": "html", "date": "4"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["indexed"] == 5
    assert body["data"]["index_name"] == ["myidx-html-3"]  # 더미 리턴값이므로 고정
    assert body["data"]["alias_name"] == "myalias"

    svc_html.index.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.index.assert_not_called()


def test_index_all_calls_both_and_returns_last(client, svc_html, svc_tsv):
    """
    source=all 이면 FileType.__members__ 순서(html, tsv)로 두 서비스를 호출.
    구현상 마지막 호출(tsv)의 반환값이 응답 data에 담긴다.
    """
    r = client.post("/api/index", json={"source": "all", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["index_name"] == ["myidx-tsv-3"]
    assert body["data"]["indexed"] == 7

    svc_html.index.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.index.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)


def test_index_invalid_source_returns_500(client, svc_html, svc_tsv):
    """
    잘못된 source 값은 FileType(...) 캐스팅에서 ValueError → 현재 구현상 500을 반환.
    """
    r = client.post("/api/index", json={"source": "pdf", "date": "3"})
    assert r.status_code == 500

    svc_html.index.assert_not_called()
    svc_tsv.index.assert_not_called()
