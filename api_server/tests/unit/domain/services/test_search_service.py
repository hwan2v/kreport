# api_server/tests/unit/domain/test_search_service.py

from unittest.mock import MagicMock
import pytest

from api_server.app.domain.services.search_service import SearchService


@pytest.fixture
def mock_searcher():
    return MagicMock()


@pytest.fixture
def service(mock_searcher):
    return SearchService(searcher=mock_searcher)


def test_search_calls_searcher_with_defaults(service, mock_searcher):
    # given
    mock_searcher.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

    # when
    res = service.search(query="카카오뱅크")  # size/explain 기본값 사용

    # then
    assert res == {"hits": {"total": {"value": 0}, "hits": []}}
    mock_searcher.search.assert_called_once_with("카카오뱅크", 3, False)


def test_search_overrides_params(service, mock_searcher):
    # given
    mock_searcher.search.return_value = {"hits": {"total": {"value": 2}, "hits": [{"_id": "1"}, {"_id": "2"}]}}

    # when
    res = service.search(query="삼성전자", size=10, explain=True)

    # then
    assert res["hits"]["total"]["value"] == 2
    assert len(res["hits"]["hits"]) == 2
    mock_searcher.search.assert_called_once_with("삼성전자", 10, True)


def test_search_propagates_exception(service, mock_searcher):
    # given: 검색 포트가 예외를 던지면 서비스도 그대로 전파해야 함
    mock_searcher.search.side_effect = RuntimeError("opensearch down")

    # when / then
    with pytest.raises(RuntimeError) as ei:
        _ = service.search("네이버", size=5)

    assert "opensearch down" in str(ei.value)
