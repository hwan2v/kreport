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
    """
    기본 파라미터(size=3, explain=False)가 적용되어 서비스가 호출되는지 검증
    """

    # given
    mock_searcher.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

    # when
    res = service.search(query="카카오뱅크")

    # then
    assert res == {"hits": {"total": {"value": 0}, "hits": []}}
    mock_searcher.search.assert_called_once_with("카카오뱅크", 3, False)


def test_search_overrides_params(service, mock_searcher):
    """
    size, explain 파라미터를 오버라이드 했을 때 서비스가 같은 값으로 호출되는지
    """

    # given
    mock_searcher.search.return_value = {"hits": {"total": {"value": 2}, "hits": [{"_id": "1"}, {"_id": "2"}]}}

    # when
    res = service.search(query="삼성전자", size=10, explain=True)

    # then
    assert res["hits"]["total"]["value"] == 2
    assert len(res["hits"]["hits"]) == 2
    mock_searcher.search.assert_called_once_with("삼성전자", 10, True)


def test_search_propagates_exception(service, mock_searcher):
    """
    검색 포트가 예외를 던지면 서비스도 그대로 전파해야 함
    """

    # given: 검색 포트가 예외를 던지면 서비스도 그대로 전파해야 함
    mock_searcher.search.side_effect = RuntimeError("opensearch down")

    # when / then
    with pytest.raises(RuntimeError) as ei:
        _ = service.search("네이버", size=5)

    assert "opensearch down" in str(ei.value)
