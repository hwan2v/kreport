from datetime import datetime, timedelta, timezone
import pytest

from api_server.app.domain.models import (
    Collection,
    FileType,
    SourceRef,
    RawDocument,
    ParsedBlock,
    ParsedDocument,
    NormalizedChunk,
    IndexErrorItem,
    IndexResult,
    AliasResult,
)

def test_enums_basic():
    # Enum 값과 캐스팅 동작
    assert Collection.wiki.value == "wiki"
    assert Collection("qna") is Collection.qna
    assert FileType.html.value == "html"
    assert FileType("tsv") is FileType.tsv

def test_raw_document_defaults_and_types():
    """
    파일 타입 식별: 확장자별로 FileType, collection이 맞게 매핑되는지 체크.
    """

    s = SourceRef(uri="file:///tmp/doc.html", file_type=FileType.html)
    r = RawDocument(source=s, body_text="<html/>", encoding="utf-8", collection=Collection.wiki)
    assert r.source is s
    assert r.collection == Collection.wiki
    assert isinstance(r.fetched_at, datetime)


def test_parsed_block_defaults_and_meta():
    """
    ParsedBlock 기본값 검증.
    """

    b = ParsedBlock()  # 기본값 사용
    assert b.type == "paragraph"  # 기본 type
    assert b.text is None
    assert isinstance(b.meta, dict) and b.meta == {}

    b2 = ParsedBlock(type="row", text=None, meta={"id": "1"})
    assert b2.type == "row"
    assert b2.meta["id"] == "1"


def test_parsed_document_structure():
    """
    ParsedDocument 구조 검증.
    """
    s = SourceRef(uri="file:///tmp/wiki.html", file_type=FileType.html)
    blocks = [
        ParsedBlock(type="body", text="본문", meta={}),
        ParsedBlock(type="summary", text="요약", meta={}),
    ]
    d = ParsedDocument(
        source=s, title="제목", blocks=blocks, lang="ko", meta={"foo": 1}, collection=Collection.wiki
    )
    assert d.title == "제목"
    assert d.lang == "ko"
    assert d.collection == Collection.wiki
    assert len(d.blocks) == 2
    assert d.blocks[0].type == "body"
    assert d.meta["foo"] == 1


def test_normalized_chunk_minimal_required_and_fields():
    """
    NormalizedChunk 필수 필드 검증.
    """
    now = datetime(2024, 1, 1, 0, 0, 0)
    c = NormalizedChunk(
        source_id="src_1",
        source_path="file:///tmp/wiki.html",
        file_type="html",          # 주의: 모델 정의가 str 타입임 (Enum 아님)
        collection="wiki",         # 주의: 모델 정의가 str 타입임 (Enum 아님)
        title="제목",
        body="본문",
        summary=None,
        infobox=None,
        paragraph=None,
        question=None,
        answer=None,
        features={"body": 0.5},
        title_embedding=None,
        body_embedding=None,
        created_date=now,
        updated_date=now,
        author="alice",
        published=True,
    )
    assert c.source_id == "src_1"
    assert c.file_type == "html"
    assert c.collection == "wiki"
    assert c.title == "제목"
    assert isinstance(c.created_date, datetime)
    assert c.created_date == c.updated_date
    assert c.features == {"body": 0.5}
    # 직렬화 가능
    dumped = c.model_dump()
    assert dumped["source_id"] == "src_1"
    assert dumped["published"] is True


def test_normalized_chunk_requires_mandatory_fields():
    """
    NormalizedChunk 누락 필드 검증
    """
    now = datetime.utcnow()
    # 필수 필드 누락 시 검증 에러
    with pytest.raises(Exception):
        _ = NormalizedChunk(
            source_path="path",
            file_type="html",
            collection="wiki",
            created_date=now,
            updated_date=now,
            published=True,
        )


def test_index_error_item_and_result_defaults():
    """
    IndexErrorItem 기본값 검증.
    """

    err = IndexErrorItem(doc_id="a1", seq=0, reason="mapper_parsing_exception")
    res = IndexResult(indexed=3, errors=[err])

    assert res.indexed == 3
    assert len(res.errors) == 1
    assert res.errors[0].doc_id == "a1"
    assert "mapper_parsing_exception" in res.errors[0].reason

    # errors 기본값은 빈 리스트
    res2 = IndexResult(indexed=0)
    assert res2.errors == []


def test_index_result_indexed_ge_0_validation():
    """
    IndexResult indexed 필드 ge=0 제약 검증.
    """

    with pytest.raises(Exception):
        _ = IndexResult(indexed=-1)  # ge=0 제약 위반


def test_alias_result_shape():
    """
    AliasResult 필드 구조 검증.
    """

    ar = AliasResult(index_name=["idx-a", "idx-b"], alias_name="myalias")
    assert ar.alias_name == "myalias"
    assert ar.index_name == ["idx-a", "idx-b"]

    ar2 = AliasResult(index_name=[], alias_name="alias")
    assert ar2.index_name == []
    assert ar2.alias_name == "alias"
