# api_server/tests/unit/adapters/parsers/test_qna_parser.py

import pytest
from pathlib import Path

from api_server.app.adapters.parsers.qna_parser import QnaParser
from api_server.app.domain.models import (
    RawDocument,
    ParsedDocument,
    ParsedBlock,
    SourceRef,
    FileType,
    Collection,
)
from api_server.app.platform.exceptions import DomainError

"""
정상 파싱: 행이 ParsedBlock(type="row", text=None, meta=dict) 로 생성되고, 전체 메타(rows, columns)가 맞는지.

공백 정리: 각 컬럼 값의 앞뒤 공백이 제거되는지.

헤더 검증: 필수 컬럼 누락 시 ValueError 발생 및 메시지 확인.

빈 입력 처리: 빈 문자열 입력 시 누락 컬럼 전체가 감지되는지.

메타데이터 보존: RawDocument의 source/collection이 결과에 그대로 반영되는지.
"""

# 테스트에서 사용할 컬렉션(이름은 프로젝트 Enum에 맞춰 조정)
TEST_COLLECTION = getattr(Collection, "qna", None) or getattr(Collection, "wiki", None)


def make_raw(tsv_text: str, uri: str = "file:///tmp/qna.tsv") -> RawDocument:
    """간단한 RawDocument 생성 헬퍼"""
    return RawDocument(
        source=SourceRef(uri=uri, file_type=FileType.tsv),
        body_text=tsv_text,
        encoding="utf-8",
        collection=TEST_COLLECTION,
    )


def test_parse_valid_tsv_returns_blocks():
    parser = QnaParser()
    tsv = (
        "id\tquestion\tanswer\tpublished\tuser_id\n"
        "1\t지구 반경?\t약 6371km\tY\tuser1\n"
        "2\t빛의 속도?\t299792458 m/s\tY\tuser2\n"
    )

    raw = make_raw(tsv)
    doc: ParsedDocument = parser.parse(raw)

    # 기본 형태 검증
    assert isinstance(doc, ParsedDocument)
    assert doc.source.uri == raw.source.uri
    assert doc.collection == TEST_COLLECTION

    # 블록(행) 파싱 검증
    assert len(doc.blocks) == 2
    for b in doc.blocks:
        assert b.type == "row"
        assert b.text is None
        assert isinstance(b.meta, dict)

    # 첫 번째 행 내용 확인
    first: ParsedBlock = doc.blocks[0]
    assert first.meta["id"] == "1"
    assert first.meta["question"] == "지구 반경?"
    assert first.meta["answer"] == "약 6371km"
    assert first.meta["published"] == "Y"
    assert first.meta["user_id"] == "user1"

    # 메타 정보(행/열)
    assert doc.meta["rows"] == 2
    cols = set(doc.meta["columns"])
    assert {"id", "question", "answer", "published", "user_id"}.issubset(cols)


def test_parse_strips_whitespace_in_values():
    parser = QnaParser()
    tsv = (
        "id\tquestion\tanswer\tpublished\tuser_id\n"
        "1\t  지구 반경? \t 약 6371km \t Y \t user1 \n"
    )

    raw = make_raw(tsv)
    doc = parser.parse(raw)

    assert len(doc.blocks) == 1
    row = doc.blocks[0].meta
    # 앞뒤 공백이 제거되었는지 확인
    assert row["question"] == "지구 반경?"
    assert row["answer"] == "약 6371km"
    assert row["published"] == "Y"
    assert row["user_id"] == "user1"


def test_parse_raises_when_missing_required_columns():
    parser = QnaParser()
    # user_id 컬럼 누락
    tsv = (
        "id\tquestion\tanswer\tpublished\n"
        "1\tQ\tA\tY\n"
    )
    raw = make_raw(tsv)

    with pytest.raises(DomainError) as ei:
        _ = parser.parse(raw)

    msg = str(ei.value)
    # 에러 메시지에 누락 컬럼명이 포함되어야 함
    assert "user_id" in msg
    assert "missing" in msg.lower()


def test_parse_raises_on_empty_text():
    parser = QnaParser()
    raw = make_raw("")  # 헤더조차 없음 → REQUIRED_COLS 전부 누락

    with pytest.raises(DomainError) as ei:
        _ = parser.parse(raw)

    msg = str(ei.value)
    for col in ["id", "question", "answer", "published", "user_id"]:
        assert col in msg


def test_parse_keeps_document_metadata():
    """원본 RawDocument의 메타데이터(소스/컬렉션)가 보존되는지 확인"""
    parser = QnaParser()
    tsv = (
        "id\tquestion\tanswer\tpublished\tuser_id\n"
        "10\tQ\tA\tY\tu\n"
    )
    raw = make_raw(tsv, uri="file:///var/data/qna.tsv")
    doc = parser.parse(raw)

    assert doc.source.uri == "file:///var/data/qna.tsv"
    assert doc.source.file_type == FileType.tsv
    assert doc.collection == TEST_COLLECTION
