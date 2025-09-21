# api_server/tests/unit/adapters/indexers/test_opensearch_indexer.py

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from unittest.mock import MagicMock, call, patch
import pytest

from api_server.app.adapters.indexers.opensearch_indexer import OpenSearchIndexer
from api_server.app.domain.models import IndexResult, AliasResult, IndexErrorItem
"""
create_index: 인덱스 존재/미존재 분기, indices.create 호출 여부 검증
_index: helpers.bulk 모킹으로 성공/에러 케이스 검증(duck typing DummyChunk로 Pydantic 의존 제거)
index(JSONL): 파일을 만들고 published 필터가 동작하는지 검증(NormalizedChunk를 더미 클래스로 패치)
delete_alias / add_alias: alias 존재 분기, 존재하지 않는 인덱스 스킵
rotate_alias_to_latest:
버전 규칙에 맞는 최신 인덱스 선택
기존 alias 제거 + 최신으로 추가 (atomic switch)
delete_old=True면 나머지 삭제 호출
엣지 케이스(패턴 조회 실패, 최신 없음, alias 없음) 처리
참고: rotate_alias_to_latest 함수의 타이핑/문서 주석에 “List[str] 반환” 서술이 있지만 실제 코드는 AliasResult를 반환합니다. 테스트는 실제 반환(AliasResult) 기준으로 검증했어요.
"""

# ----------------------
# 헬퍼: Dummy Chunk (duck typing)
# ----------------------
class DummyChunk:
    def __init__(self, source_id: str, payload: Dict[str, Any]):
        self.source_id = source_id
        self._payload = payload

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return self._payload


# ----------------------
# 공용 픽스처
# ----------------------
@pytest.fixture
def mock_client():
    """OpenSearch 클라이언트 목 객체 (indices 네임스페이스 포함)"""
    client = MagicMock()
    client.indices = MagicMock()
    return client


@pytest.fixture
def indexer(mock_client, monkeypatch):
    """_load_index_schema를 우회해서 파일 접근 없이 indexer 생성"""
    with patch.object(OpenSearchIndexer, "_load_index_schema") as mock_loader:
        inst = OpenSearchIndexer(client=mock_client, prefix_index_name="myidx", alias_name="myalias")
        inst.index_schema = {"settings": {}, "mappings": {}}  # 스키마는 빈 값으로
    return inst


# ----------------------
# create_index
# ----------------------
def test_create_index_when_not_exists(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists.return_value = False

    name = indexer.create_index(source="html", index_date="3")

    assert name == "myidx-html-3"
    mock_client.indices.exists.assert_called_once_with(index="myidx-html-3")
    mock_client.indices.create.assert_called_once_with(index="myidx-html-3", body=indexer.index_schema)


def test_create_index_when_exists(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists.return_value = True

    name = indexer.create_index(source="tsv", index_date="9")

    assert name == "myidx-tsv-9"
    mock_client.indices.exists.assert_called_once_with(index="myidx-tsv-9")
    mock_client.indices.create.assert_not_called()


# ----------------------
# _index (bulk)
# ----------------------
def test__index_bulk_success(indexer: OpenSearchIndexer, mock_client: MagicMock, monkeypatch):
    chunks = [
        DummyChunk("a1", {"foo": 1}),
        DummyChunk("a2", {"bar": 2}),
        DummyChunk("a3", {"baz": 3}),
    ]

    # helpers.bulk 모킹: ok=3, errors=[]
    with patch("api_server.app.adapters.indexers.opensearch_indexer.helpers.bulk") as mock_bulk:
        mock_bulk.return_value = (3, [])
        result: IndexResult = indexer._index("myidx-html-3", chunks)

    assert isinstance(result, IndexResult)
    assert result.indexed == 3
    assert result.errors == []
    # bulk 호출 시 generator(actions())가 넘어가므로 _index 내부 동작은 mock 호출로만 검증
    mock_bulk.assert_called_once()
    args, kwargs = mock_bulk.call_args
    # 첫번째 인수: client, 두번째: actions(generator)
    assert args[0] is mock_client


def test__index_bulk_with_errors(indexer: OpenSearchIndexer, mock_client: MagicMock):
    chunks = [DummyChunk("e1", {"x": 1})]

    # 에러 목록 형태는 다양할 수 있으나, 코드가 참조하는 구조에 맞춰 구성
    bulk_errors = [
        {"index": {"_id": "e1", "status": 400, "error": {"type": "mapper_parsing_exception"}}}
    ]

    with patch("api_server.app.adapters.indexers.opensearch_indexer.helpers.bulk") as mock_bulk:
        mock_bulk.return_value = (0, bulk_errors)
        result: IndexResult = indexer._index("myidx-html-3", chunks)

    assert result.indexed == 0
    assert len(result.errors) == 1
    err: IndexErrorItem = result.errors[0]
    assert err.doc_id == "e1"
    assert "mapper_parsing_exception" in err.reason


# ----------------------
# index(resource_file_path) - JSONL 읽기 경로
#  -> NormalizedChunk.model_validate 호출이 있어 실제 모델 의존이 큼
#  -> 여기서는 _index를 패치해 "들어온 chunks 개수"만 검증
# ----------------------
def test_index_reads_jsonl_and_filters_published(indexer: OpenSearchIndexer, tmp_path: Path, monkeypatch):
    # JSONL: 첫 줄은 published=True, 둘째 줄은 published=False → 한 개만 인덱싱
    p = tmp_path / "data.jsonl"
    docs = [
        {"source_id": "ok1", "published": True, "payload": {"a": 1}},
        {"source_id": "ng1", "published": False, "payload": {"a": 2}},
    ]
    p.write_text("\n".join(json.dumps(d) for d in docs), encoding="utf-8")

    # NormalizedChunk.model_validate를 더미로 교체 (duck typing DummyChunk로 대체)
    class DummyNormalizedChunk(DummyChunk):
        @classmethod
        def model_validate(cls, doc: Dict[str, Any]):
            # published True만 들어오게 됨(상위 filter)
            return cls(source_id=doc["source_id"], payload=doc.get("payload", {}))

    # opensearch_indexer 모듈에서 NormalizedChunk를 Dummy로 패치
    with patch("api_server.app.adapters.indexers.opensearch_indexer.NormalizedChunk", DummyNormalizedChunk):
        captured = {}

        # _index를 가로채서 넘어온 chunks 개수만 기록
        def fake__index(index_name: str, chunks: Iterable[DummyNormalizedChunk]):
            items = list(chunks)
            captured["count"] = len(items)
            return IndexResult(indexed=len(items), errors=[])

        with patch.object(indexer, "_index", side_effect=fake__index):
            res = indexer.index(index_name="myidx-html-3", resource_file_path=str(p))

    assert isinstance(res, IndexResult)
    # published=True 인 것만 1개
    assert res.indexed == 1
    assert captured["count"] == 1


# ----------------------
# alias 조작
# ----------------------
def test_delete_alias_when_exists(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists_alias.return_value = True

    indexer.delete_alias("myalias")

    mock_client.indices.exists_alias.assert_called_once_with(name="myalias")
    mock_client.indices.delete_alias.assert_called_once_with(name="myalias", index="_all")


def test_delete_alias_when_not_exists(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists_alias.return_value = False

    indexer.delete_alias("myalias")

    mock_client.indices.delete_alias.assert_not_called()


def test_add_alias_for_existing_indices(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists_alias.return_value = False
    mock_client.indices.exists.side_effect = [True, True]

    ret = indexer.add_alias("myalias", ["myidx-html-3", "myidx-tsv-2"])

    assert ret == "myalias"
    assert mock_client.indices.put_alias.call_args_list == [
        call(index="myidx-html-3", name="myalias"),
        call(index="myidx-tsv-2", name="myalias"),
    ]


def test_add_alias_skips_missing_index(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.exists_alias.return_value = False
    mock_client.indices.exists.side_effect = [True, False]

    indexer.add_alias("myalias", ["myidx-html-3", "missing-idx"])

    mock_client.indices.put_alias.assert_called_once_with(index="myidx-html-3", name="myalias")


# ----------------------
# rotate_alias_to_latest
# ----------------------
def test_rotate_alias_to_latest_updates_alias_and_deletes_old(indexer: OpenSearchIndexer, mock_client: MagicMock):
    """
    인덱스 네이밍: {base_prefix}-{group}-{ver}
      - myidx-html-1, myidx-html-3, myidx-tsv-2 → 최신은 html-3, tsv-2
    """
    # 패턴 get
    mock_client.indices.get.return_value = {
        "myidx-html-1": {},
        "myidx-html-3": {},
        "myidx-tsv-2": {},
        "myidx-zzz-bad": {},  # 패턴과 맞지 않아 스킵될 항목
    }

    # 기존 alias가 존재하며 다른 인덱스를 가리키고 있었다고 가정
    mock_client.indices.exists_alias.return_value = True
    mock_client.indices.get_alias.return_value = {
        "myidx-html-1": {"aliases": {"myalias": {}}},
        "myidx-tsv-1": {"aliases": {"myalias": {}}},
    }

    result: AliasResult = indexer.rotate_alias_to_latest(
        alias_name="myalias", base_prefix="myidx", delete_old=True
    )

    # update_aliases가 remove+add 조합으로 한 번 호출
    mock_client.indices.update_aliases.assert_called_once()
    body = mock_client.indices.update_aliases.call_args.kwargs["body"]
    actions = body["actions"]

    # remove: 기존 연결 2개
    removes = [a for a in actions if "remove" in a]
    assert {"index": "myidx-html-1", "alias": "myalias"} in [x["remove"] for x in removes]
    assert {"index": "myidx-tsv-1", "alias": "myalias"} in [x["remove"] for x in removes]

    # add: 최신 인덱스 2개(html-3, tsv-2)
    adds = [a for a in actions if "add" in a]
    add_targets = [x["add"]["index"] for x in adds]
    assert set(add_targets) == {"myidx-html-3", "myidx-tsv-2"}

    # delete_old=True → 최신 외 나머지 삭제 호출
    deleted = {c.kwargs.get("index") for c in mock_client.indices.delete.mock_calls}
    # myidx-zzz-bad도 전체 목록에는 있지만 패턴 불일치로 latest_by_group에 포함 안 되므로 삭제 후보
    assert {"myidx-html-1", "myidx-zzz-bad"}.issubset(deleted)

    # 반환 객체 확인
    assert isinstance(result, AliasResult)
    assert set(result.index_name) == {"myidx-html-3", "myidx-tsv-2"}
    assert result.alias_name == "myalias"


def test_rotate_alias_to_latest_no_indices(indexer: OpenSearchIndexer, mock_client: MagicMock):
    mock_client.indices.get.side_effect = Exception("not found")

    result = indexer.rotate_alias_to_latest(alias_name="myalias", base_prefix="nope", delete_old=True)
    # 예외 발생 시 [] 반환 설계에 맞춰 검증 (코드 원문 주석과 타입 힌트 상 괴리가 있어 List/AliasResult 혼용됨)
    assert result == []


def test_rotate_alias_to_latest_no_latest_found(indexer: OpenSearchIndexer, mock_client: MagicMock):
    # 패턴은 찾았으나 버전 패턴에 매칭되는 이름이 없음
    mock_client.indices.get.return_value = {
        "myidx-badname": {},
        "myidx-also-bad": {},
    }
    result = indexer.rotate_alias_to_latest(alias_name="myalias", base_prefix="myidx", delete_old=False)
    assert result == []


def test_rotate_alias_to_latest_when_alias_absent(indexer: OpenSearchIndexer, mock_client: MagicMock):
    # 최신 계산은 가능
    mock_client.indices.get.return_value = {
        "myidx-html-1": {},
        "myidx-html-2": {},
        "myidx-tsv-3": {},
    }
    mock_client.indices.exists_alias.return_value = False  # 기존 alias 없음

    _ = indexer.rotate_alias_to_latest(alias_name="myalias", base_prefix="myidx", delete_old=False)

    # remove 없이 add 만 호출되었는지 확인
    body = mock_client.indices.update_aliases.call_args.kwargs["body"]
    actions = body["actions"]
    assert all("add" in a for a in actions)
    add_targets = [a["add"]["index"] for a in actions]
    assert set(add_targets) == {"myidx-html-2", "myidx-tsv-3"}
