# api_server/tests/integration/test_api_extract.py

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from api_server.app.main import app
from api_server.app.api.deps import get_pipeline_resolver
from api_server.app.domain.models import FileType, Collection

"""
Depends(get_pipeline_resolver) 를 dependency_overrides 로 대체해 통합 관점에서 테스트.
source=tsv/html 일 때 각각 올바른 Collection 매핑(qna/wiki)과 호출 파라미터를 검증.
source=all 일 때 두 서비스 모두 호출되며, 구현 특성상 **마지막 호출(tsv)**의 결과가 응답 data에 담기는 점을 검증.
    잘못된 source는 현재 구현상 500 에러가 발생함을 명시적으로 테스트하여, 후속으로 예외 처리/검증 로직 개선 근거로 활용 가능
"""

class DummyResolver:
    """
    routers.extract 에서 resolver.for_type(FileType) 로 서비스를 받는 것을 흉내내는 간단한 DI 대역
    """
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
    r = client.post("/api/extract", json={"source": "tsv", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    print(body)
    assert body["success"] is True
    assert body["message"].startswith("문서 추출 후 저장")
    # 반환 데이터는 서비스가 돌려준 파일명(엔드포인트 구현)
    assert body["data"] == {'tsv': 'qna_3_parsed.json'}

    # 호출 검증
    svc_tsv.extract.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)
    svc_html.extract.assert_not_called()


def test_extract_single_html(client, svc_html, svc_tsv):
    """
    source=html 이면 HTML용 서비스만 호출되고, 컬렉션 매핑은 wiki 이어야 한다.
    """
    r = client.post("/api/extract", json={"source": "html", "date": "4"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # todo.
    assert body["data"] == {'html': 'wiki_3_parsed.json'}

    svc_html.extract.assert_called_once_with(source="html", date="4", collection=Collection.wiki)
    svc_tsv.extract.assert_not_called()


def test_extract_all_calls_both_and_returns_last(client, svc_html, svc_tsv):
    """
    source=all 이면 FileType.__members__ 순서(html, tsv)로 두 서비스를 다 호출.
    구현상 마지막 호출의 결과가 data에 담겨 반환된다(tsv가 마지막).
    """
    r = client.post("/api/extract", json={"source": "all", "date": "3"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # 마지막에 호출된 tsv 서비스의 반환값이어야 함
    assert body["data"] == {'html': 'wiki_3_parsed.json', 'tsv': 'qna_3_parsed.json'}

    svc_html.extract.assert_called_once_with(source="html", date="3", collection=Collection.wiki)
    svc_tsv.extract.assert_called_once_with(source="tsv", date="3", collection=Collection.qna)


def test_extract_invalid_source_returns_500(client, svc_html, svc_tsv):
    """
    잘못된 source 값을 넣으면 라우터 내부에서 FileType(...) 변환 시 ValueError가 발생하여 422 리턴
    (엔드포인트 구현에 try/except가 없기 때문)
    """
    r = client.post("/api/extract", json={"source": "pdf", "date": "3"})
    # 422 Unprocessable Entity 반환환
    assert r.status_code == 422

    # 호출 자체가 일어나지 않아야 함
    svc_html.extract.assert_not_called()
    svc_tsv.extract.assert_not_called()
