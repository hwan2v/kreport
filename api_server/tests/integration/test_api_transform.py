from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection
from api_server.app.platform.exceptions import DomainError, ResourceNotFound


class DummyResolver:
    """routers.transform 에서 resolver.for_type(FileType)로 서비스 반환을 흉내내는 mockup"""
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
    m.transform.return_value = "wiki_3_normalized.json"
    return m


@pytest.fixture
def svc_tsv():
    m = MagicMock()
    m.transform.return_value = "qna_3_normalized.json"
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


def test_transform_invalid_source_returns_422(client, svc_html, svc_tsv):
    """
    잘못된 source 값은 FileType(...) 캐스팅에서 ValueError -> 422 리턴
    """
    r = client.post("/api/transform", json={"source": "pdf", "date": "3"})
    assert r.status_code == 422

    svc_html.transform.assert_not_called()
    svc_tsv.transform.assert_not_called()


def test_transform_not_found_resource_returns_404(client, svc_html, svc_tsv):
    """
    파싱 파일이 없는 경우 ResourceNotFound 예외가 발생하여 404 리턴
    """
    svc_html.transform.side_effect = ResourceNotFound(
        resource="html/day_4",
        detail="No files for date=4",
    )
    r = client.post("/api/transform", json={"source": "html", "date": "4"})
    assert r.status_code == 404

    svc_html.transform.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.transform.assert_not_called()


def test_transform_unknown_error_returns_400(client, svc_html, svc_tsv):
    """
    임의 DomainError 예외가 발생하면 400 리턴
    """
    svc_html.transform.side_effect = DomainError("unknown error")
    r = client.post("/api/transform", json={"source": "html", "date": "3"})
    assert r.status_code == 400

    svc_html.transform.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.transform.assert_not_called()
