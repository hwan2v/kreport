# api_server/tests/unit/domain/test_index_service.py

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call
import json
import pytest

from api_server.app.domain.services.index_service import IndexService  # 파일 경로가 search_service.py임에 주의
from api_server.app.domain.models import (
    Collection,
    FileType,
    SourceRef,
    RawDocument,
    ParsedDocument,
    ParsedBlock,
    NormalizedChunk,
    IndexResult,
    AliasResult,
)
"""
extract()
    ListenPort.listen으로 받은 리소스들을 FetchPort.fetch → ParsePort.parse 순으로 호출하는지.
    결과가 qna_3_parsed.json 같은 JSONL 파일로 저장되는지(줄 수/내용 확인).
transform()
    Transformer.read_parsed_document가 올바른 경로로 호출되는지.
    Transformer.transform 결과가 *_normalized.json으로 저장되는지.
index()
    Indexer.create_index → Indexer.index → Indexer.rotate_alias_to_latest가 순서대로 호출되는지.
    반환 결과가 두 결과 dict의 병합 형태인지.
헬퍼
    _get_resource_dir_path, _create_file_name 규칙 검증.
"""

# ---------------------------
# Helpers
# ---------------------------
def make_parsed_doc(uri: str, rows: list[dict], collection=Collection.wiki):
    """row(meta dict)들을 가진 ParsedDocument 생성"""
    blocks = [ParsedBlock(type="row", text=None, meta=r) for r in rows]
    return ParsedDocument(
        source=SourceRef(uri=uri, file_type=FileType.tsv, headers=None),
        title=None,
        blocks=blocks,
        lang=None,
        meta={"rows": len(rows)},
        collection=collection,
    )


def make_chunk(source_id="tsv_1", uri="file:///data/day_3/qna.tsv", collection="qna"):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return NormalizedChunk(
        source_id=source_id,
        source_path=uri,
        file_type="tsv",          # NormalizedChunk는 str 타입
        collection=collection,    # NormalizedChunk는 str 타입
        title=None,
        body=None,
        summary=None,
        infobox=None,
        paragraph=None,
        question="Q",
        answer="A",
        features=None,
        title_embedding=None,
        body_embedding=None,
        created_date=now,
        updated_date=now,
        author="alice",
        published=True,
    )


# ---------------------------
# Fixtures
# ---------------------------
@pytest.fixture
def ports():
    """IndexService에 주입할 포트 목 객체들"""
    listener = MagicMock()
    fetcher = MagicMock()
    parser = MagicMock()
    transformer = MagicMock()
    indexer = MagicMock()
    return listener, fetcher, parser, transformer, indexer


@pytest.fixture
def service(ports):
    listener, fetcher, parser, transformer, indexer = ports
    return IndexService(
        listener=listener, fetcher=fetcher, parser=parser, transformer=transformer, indexer=indexer
    )


# ---------------------------
# extract()
# ---------------------------
def test_extract_writes_parsed_jsonl_and_calls_ports(tmp_path: Path, service: IndexService, ports):
    listener, fetcher, parser, transformer, indexer = ports

    # 리스너가 소스 파일 경로를 돌려줌
    resource_files = [
        "file:///data/day_3/qna.tsv",
        "file:///data/day_3/qna2.tsv",
    ]
    listener.listen.return_value = resource_files

    # fetch → RawDocument
    raw1 = RawDocument(
        source=SourceRef(uri=resource_files[0], file_type=FileType.tsv),
        body_text="id\tquestion\tanswer\tpublished\tuser_id\n1\tQ\tA\tY\tu\n",
        encoding="utf-8",
        collection=Collection.qna,
    )
    raw2 = RawDocument(
        source=SourceRef(uri=resource_files[1], file_type=FileType.tsv),
        body_text="id\tquestion\tanswer\tpublished\tuser_id\n2\tQ2\tA2\tY\tu2\n",
        encoding="utf-8",
        collection=Collection.qna,
    )
    fetcher.fetch.side_effect = [raw1, raw2]

    # parser → ParsedDocument (간단히 row 1개씩)
    pd1 = make_parsed_doc(resource_files[0], rows=[{"id": "1", "question": "Q", "answer": "A", "published": "Y", "user_id": "u"}], collection=Collection.qna)
    pd2 = make_parsed_doc(resource_files[1], rows=[{"id": "2", "question": "Q2", "answer": "A2", "published": "Y", "user_id": "u2"}], collection=Collection.qna)
    parser.parse.side_effect = [pd1, pd2]

    # out_dir을 테스트 폴더로 강제
    # _get_resource_dir_path는 "api_server/resources/data/{source}/day_{date}" 를 반환하므로 테스트에 맞게 패치
    service._get_resource_dir_path = lambda source, date: str(tmp_path / f"{source}/day_{date}")

    out_name = service.extract(source="tsv", date="3", collection=Collection.qna)

    # 파일 경로 확인
    expected_dir = tmp_path / "tsv" / "day_3"
    expected_file = expected_dir / "qna_3_parsed.json"
    assert out_name == expected_file.name  # 메서드는 파일명만 반환
    assert expected_file.exists()

    # 내용: JSONL 2줄
    lines = [l for l in expected_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2

    # 포트 호출 검증
    listener.listen.assert_called_once_with("tsv", "3", extension="tsv")
    fetcher.fetch.assert_has_calls([call(resource_files[0], Collection.qna), call(resource_files[1], Collection.qna)])
    assert parser.parse.call_count == 2


# ---------------------------
# transform()
# ---------------------------
def test_transform_reads_parsed_and_writes_normalized(tmp_path: Path, service: IndexService, ports):
    listener, fetcher, parser, transformer, indexer = ports

    service._get_resource_dir_path = lambda source, date: str(tmp_path / f"{source}/day_{date}")

    # transformer.read_parsed_document 는 파일 경로를 받고 ParsedDocument 리스트 반환
    pd = make_parsed_doc("file:///data/day_3/qna.tsv", rows=[{"id": "1", "question": "Q", "answer": "A", "published": "Y", "user_id": "u"}], collection=Collection.qna)
    transformer.read_parsed_document.return_value = [pd]

    # transformer.transform 는 NormalizedChunk 이터러블 반환
    chunk = make_chunk(source_id="tsv_1", uri="file:///data/day_3/qna.tsv", collection="qna")
    transformer.transform.return_value = [chunk]

    out_name = service.transform(source="tsv", date="3", collection=Collection.qna)
    expected_dir = service._get_resource_dir_path("tsv", "3")
    parsed_path = service._create_file_name(Collection.qna, "3", suffix="parsed", out_dir=expected_dir)
    normalized_path = Path(expected_dir) / "qna_3_normalized.json"

    # read_parsed_document가 올바른 경로로 호출되었는지
    transformer.read_parsed_document.assert_called_once_with(parsed_path)

    # 출력 파일 생성 확인 (파일명만 반환)
    assert out_name == normalized_path.name
    assert normalized_path.exists()

    # 내용: JSONL 1줄
    lines = [l for l in normalized_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    parsed_json = json.loads(lines[0])
    assert parsed_json["source_id"] == "tsv_1"
    assert parsed_json["collection"] == "qna"


# ---------------------------
# index()
# ---------------------------
def test_index_creates_indexes_and_rotates_alias(tmp_path: Path, service: IndexService, ports):
    listener, fetcher, parser, transformer, indexer = ports

    # index()는 normalized 파일을 읽도록 Indexer에 경로를 넘김 → 실제 파일을 생성해둔다
    service._get_resource_dir_path = lambda source, date: str(tmp_path / f"{source}/day_{date}")
    out_dir = Path(service._get_resource_dir_path("tsv", "3"))
    out_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = out_dir / "qna_3_normalized.json"
    chunk = make_chunk(source_id="tsv_1", uri="file:///data/day_3/qna.tsv", collection="qna")
    normalized_path.write_text(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) + "\n", encoding="utf-8")

    # Indexer 동작 모킹
    indexer.create_index.return_value = "myidx-tsv-3"
    indexer.index.return_value = IndexResult(indexed=1, errors=[])
    indexer.rotate_alias_to_latest.return_value = AliasResult(index_name=["myidx-tsv-3"], alias_name="myalias")
    # 서비스에서 참조하는 속성 추가
    indexer.alias_name = "myalias"
    indexer.prefix_index_name = "myidx"

    result = service.index(source="tsv", date="3", collection=Collection.qna)

    # create_index 호출
    indexer.create_index.assert_called_once_with("tsv", "3")
    # index 호출(파일 경로 확인)
    
    indexer.index.assert_called_once_with("myidx-tsv-3", str(normalized_path))
    # alias 회전 호출
    indexer.rotate_alias_to_latest.assert_called_once_with("myalias", "myidx", delete_old=False)

    # 결과 병합 확인
    assert result["indexed"] == 1
    assert result["alias_name"] == "myalias"
    assert result["index_name"] == ["myidx-tsv-3"]


# ---------------------------
# 내부 헬퍼
# ---------------------------
def test_internal_filename_helpers(tmp_path: Path, service: IndexService):
    # 고정 경로 포맷 확인
    p = service._get_resource_dir_path("html", "4")
    assert p.endswith("api_server/resources/data/html/day_4")

    # 파일명 조합 확인
    fname = service._create_file_name(Collection.wiki, "7", suffix="parsed", out_dir=str(tmp_path))
    assert fname == str(Path(tmp_path) / "wiki_7_parsed.json")
