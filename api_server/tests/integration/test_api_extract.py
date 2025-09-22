from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection
from api_server.app.platform.exceptions import ResourceNotFound, DomainError


class DummyResolver:
    """routers.extract 에서 resolver.for_type(FileType)로 서비스 반환을 흉내내는 간단한 mockup"""
    
    def __init__(self, mapping):
        self._mapping = mapping

    def for_type(self, ft: FileType):
        return self._mapping[ft]


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def svc_html():
    # extract(source, date, collection) -> 파일명(or 경로) 반환처럼 동작시킴
    m = MagicMock()
    m.extract.return_value = "wiki_3_parsed.json"
    return m


@pytest.fixture
def svc_tsv():
    m = MagicMock()
    m.extract.return_value = "qna_3_parsed.json"
    return m


@pytest.fixture(autouse=True)
def override_resolver(svc_html, svc_tsv):
    """
    /extract 엔드포인트의 Depends(get_pipeline_resolver)를 오버라이드
    """
    resolver = DummyResolver(
        {
            FileType.html: svc_html,
            FileType.tsv: svc_tsv,
        }
    )
    app.dependency_overrides[get_pipeline_resolver] = lambda: resolver
    yield
    app.dependency_overrides.clear()


def test_extract_single_tsv(client, svc_html, svc_tsv):
    """
    source=tsv 이면 TSV용 서비스만 호출되고, 컬렉션 매핑은 qna 이어야 한다.
    """
    r = client.post("/v1/extract", json={"source": "tsv", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["message"].startswith("문서 추출 후 저장")
    assert body["data"] == {'tsv': 'qna_3_parsed.json'}

    # 호출 검증
    svc_tsv.extract.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)
    svc_html.extract.assert_not_called()


def test_extract_single_html(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    """
    svc_html.extract.side_effect = None
    r = client.post("/v1/extract", json={"source": "html", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {'html': 'wiki_3_parsed.json'}

    svc_html.extract.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.extract.assert_not_called()


def test_extract_all_calls_both_and_returns_last(client, svc_html, svc_tsv):
    """
    source=all 이면 FileType.__members__ 순서(html, tsv)로 두 서비스를 다 호출.
    호출 결과, html과 tsv 두 처리 결과(파일명)가 data에 담겨 반환된다.
    """
    svc_html.extract.side_effect = None
    r = client.post("/v1/extract", json={"source": "all", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # 마지막에 호출된 tsv 서비스의 반환값이어야 함
    assert body["data"] == {'html': 'wiki_3_parsed.json', 'tsv': 'qna_3_parsed.json'}

    svc_html.extract.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.extract.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)


def test_extract_invalid_date_returns_404(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    date에 해당하는 파일이 없는 경우 ResourceNotFound 예외가 발생하여 404 리턴
    """
    svc_html.extract.side_effect = ResourceNotFound(
        resource="html/day_5",
        detail="No files for date=5",
    )
    r = client.post("/v1/extract", json={"source": "html", "date": "5"})
    assert r.status_code == 404

    body = r.json()
    assert body["success"] is False

    svc_html.extract.assert_called_once_with(source="html", date="5", collection=Collection.wiki)
    svc_tsv.extract.assert_not_called()

def test_extract_invalid_date_returns_404(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    date에 해당하는 파일이 없는 경우 ResourceNotFound 예외가 발생하여 404 리턴
    """
    svc_html.extract.side_effect = ResourceNotFound(
        resource="html/day_5",
        detail="No files for date=5",
    )
    r = client.post("/v1/extract", json={"source": "html", "date": "5"})
    assert r.status_code == 404

    body = r.json()
    assert body["success"] is False

    svc_html.extract.assert_called_once_with(source="html", date="5", collection=Collection.wiki)
    svc_tsv.extract.assert_not_called()


def test_extract_invalid_source_returns_422(client, svc_html, svc_tsv):
    """
    잘못된 source 값을 넣으면 라우터 내부에서 FileType(...) 변환 시 ValueError가 발생하여 422 리턴
    (엔드포인트 구현에 try/except가 없기 때문)
    """
    r = client.post("/v1/extract", json={"source": "pdf", "date": "3"})
    # 422 Unprocessable Entity 반환환
    assert r.status_code == 422

    # 호출 자체가 일어나지 않아야 함
    svc_html.extract.assert_not_called()
    svc_tsv.extract.assert_not_called()


def test_extract_unknown_error_returns_400(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    임의 DomainError 예외가 발생시켜 400 리턴
    """
    svc_html.extract.side_effect = DomainError("unknown error")
    r = client.post("/v1/extract", json={"source": "html", "date": "3"})
    assert r.status_code == 400

    body = r.json()
    assert body["success"] is False

    svc_html.extract.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.extract.assert_not_called()