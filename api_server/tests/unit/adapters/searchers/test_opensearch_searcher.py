# api_server/tests/unit/adapters/searchers/test_opensearch_searcher.py

from unittest.mock import MagicMock
import pytest

from api_server.app.adapters.searchers.opensearch_searcher import OpenSearchSearcher


@pytest.fixture
def mock_client():
    c = MagicMock()
    return c


def test_build_query_basic_structure(mock_client):
    s = OpenSearchSearcher(client=mock_client, alias_name="my-alias")
    body = s._build_query(query="카카오뱅크")

    # 최상위
    assert body["from"] == 0
    assert body["size"] == 3
    assert body["explain"] is False
    assert body["min_score"] == 5

    # function_score 쿼리 체크
    fs = body["query"]["function_score"]
    assert "query" in fs and "functions" in fs
    assert fs["score_mode"] == "avg"
    assert fs["boost_mode"] == "sum"

    # filter: published == True
    filt = fs["query"]["bool"]["filter"]["bool"]["must"][0]["term"]
    assert filt == {"published": True}

    # should 절의 일부 필드/boost 확인
    shoulds = fs["query"]["bool"]["should"]
    # title 관련 multi_match
    title_mm = shoulds[0]["multi_match"]
    assert title_mm["fields"] == ["title", "title.keyword"]
    assert title_mm["boost"] == 4

    # question/answer 관련 multi_match
    qa_mm = shoulds[1]["multi_match"]
    assert qa_mm["fields"] == ["question", "answer"]
    assert qa_mm["boost"] == 2.5

    # infobox match
    infobox_m = shoulds[2]["match"]["infobox"]
    assert infobox_m["boost"] == 2

    # paragraph match
    para_m = shoulds[3]["match"]["paragraph"]
    assert para_m["boost"] == 2

    # summary/infobox multi_match
    summ_mm = shoulds[4]["multi_match"]
    assert summ_mm["fields"] == ["summary", "infobox"]
    assert summ_mm["boost"] == 2

    # functions 확인
    funcs = fs["functions"]
    fields = [f["field_value_factor"]["field"] for f in funcs]
    assert fields == ["features.body", "features.summary", "features.infobox"]
    # factor/missing 일부 확인
    assert funcs[0]["field_value_factor"]["factor"] == 1.5
    assert funcs[1]["field_value_factor"]["factor"] == 3
    assert funcs[2]["field_value_factor"]["factor"] == 8


def test_build_query_overrides(mock_client):
    s = OpenSearchSearcher(client=mock_client, alias_name="alias")
    body = s._build_query(query="네이버", size=10, explain=True, min_score=0.1)

    assert body["size"] == 10
    assert body["explain"] is True
    assert pytest.approx(body["min_score"], rel=1e-6) == 0.1


def test_search_calls_client_with_alias_and_body(mock_client):
    s = OpenSearchSearcher(client=mock_client, alias_name="my-search-alias")

    # 클라이언트가 반환할 결과 모킹
    mock_client.search.return_value = {"hits": {"total": {"value": 1}, "hits": [{"_id": "1"}]}}

    # 실행
    res = s.search(query="삼성전자", size=5, explain=True)

    # 결과 그대로 전달되는지
    assert res == {"hits": {"total": {"value": 1}, "hits": [{"_id": "1"}]}}

    # 호출 파라미터 검증: index는 alias, body는 _build_query 결과
    mock_client.search.assert_called_once()
    args, kwargs = mock_client.search.call_args
    assert kwargs["index"] == "my-search-alias"

    # body 내용 검증(핵심 몇 가지만)
    body = kwargs["body"]
    assert body["size"] == 5
    assert body["explain"] is True
    assert body["query"]["function_score"]["query"]["bool"]["filter"]["bool"]["must"][0]["term"] == {"published": True}
