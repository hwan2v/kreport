from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection
from api_server.app.platform.exceptions import ResourceNotFound
from opensearchpy.exceptions import ConnectionError


class DummyResolver:
    """routers.index 에서 resolver.for_type(FileType)로 서비스 반환을 흉내내는 간단한 mockup"""
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
    """
    source=tsv 이면 TSV용 서비스만 호출되고, 컬렉션 매핑은 qna 이어야 한다.
    """
    r = client.post("/api/index", json={"source": "tsv", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["message"].startswith("문서 인덱싱")
    assert body["data"]["tsv"]["indexed"] == 7
    assert body["data"]["tsv"]["index_name"] == ["myidx-tsv-3"]
    assert body["data"]["tsv"]["alias_name"] == "myalias"

    svc_tsv.index.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)
    svc_html.index.assert_not_called()


def test_index_single_html(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    """
    svc_html.index.side_effect = None
    r = client.post("/api/index", json={"source": "html", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["html"]["indexed"] == 5
    assert body["data"]["html"]["index_name"] == ["myidx-html-3"]  # 더미 리턴값이므로 고정
    assert body["data"]["html"]["alias_name"] == "myalias"

    svc_html.index.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.index.assert_not_called()


def test_index_all_calls_both_and_returns_last(client, svc_html, svc_tsv):
    """
    source=all 이면 FileType.__members__ 순서(html, tsv)로 두 서비스를 호출.
    html, tsv 두 색인 결과(색인명)가 data에 담겨 반환된다.
    """
    svc_html.index.side_effect = None
    r = client.post("/api/index", json={"source": "all", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["tsv"]["index_name"] == ["myidx-tsv-3"]
    assert body["data"]["tsv"]["indexed"] == 7
    assert body["data"]["html"]["index_name"] == ["myidx-html-3"]
    assert body["data"]["html"]["indexed"] == 5

    svc_html.index.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.index.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)


def test_index_invalid_source_returns_500(client, svc_html, svc_tsv):
    """
    잘못된 source 값은 FileType(...) 캐스팅에서 ValueError -> 422을 반환.
    """
    r = client.post("/api/index", json={"source": "pdf", "date": "3"})
    assert r.status_code == 422

    svc_html.index.assert_not_called()
    svc_tsv.index.assert_not_called()


def test_index_not_found_resource_returns_404(client, svc_html, svc_tsv):
    """
    ResourceNotFound 예외가 발생하면 404 리턴
    """
    svc_html.index.side_effect = ResourceNotFound(
        resource="html/day_4",
        detail="No files for date=4",
    )
    r = client.post("/api/index", json={"source": "html", "date": "4"})
    assert r.status_code == 404

    svc_html.index.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.index.assert_not_called()


def test_index_connection_error_returns_500(client, svc_html, svc_tsv):
    """
    ConnectionError 예외가 발생하면 500 리턴
    """
    svc_html.index.side_effect = ConnectionError("opensearch down")
    r = client.post("/api/index", json={"source": "html", "date": "4"})
    assert r.status_code == 500

    svc_html.index.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.index.assert_not_called()
