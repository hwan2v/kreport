# api_server/tests/unit/adapters/transformers/test_qna_transformer.py

from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from api_server.app.adapters.transformers.qna_transformer import QnaTransformer
from api_server.app.domain.models import (
    RawDocument,
    ParsedDocument,
    ParsedBlock,
    SourceRef,
    FileType,
    Collection,
    NormalizedChunk,
)
"""
read_parsed_document
    JSON 리스트, 딕셔너리+data, 단일 딕셔너리 3가지 입력 형식 처리.
    지원하지 않는 포맷은 ValueError 발생.
transform
    infer_date_from_path 를 monkeypatch 로 고정해 시각 필드 검증을 안정화.
    각 row가 NormalizedChunk로 매핑되는지, 필드 매핑 규칙(아이디, 작성자, 게시 여부, 파일/컬렉션)이 정확한지 확인.
    row가 아닌 블록은 무시.
    결측값 시 기본값 적용(답변 "", 작성자 None, 공개 여부 False).
"""

TEST_COLLECTION = getattr(Collection, "qna", None) or getattr(Collection, "wiki", None)


# ---------------------------
# Helpers
# ---------------------------
def make_parsed_document(
    uri: str,
    rows: list[dict],
    file_type: FileType = FileType.tsv,
    collection=TEST_COLLECTION,
    title: str | None = None,
):
    """rows(dict)의 리스트를 ParsedBlock(type='row')로 감싼 ParsedDocument 생성"""
    blocks = [ParsedBlock(type="row", text=None, meta=r) for r in rows]
    return ParsedDocument(
        source=SourceRef(uri=uri, file_type=file_type),
        title=title,
        blocks=blocks,
        lang=None,
        meta={"rows": len(rows)},
        collection=collection,
    )


# ---------------------------
# read_parsed_document()
# ---------------------------
def test_read_parsed_document_from_list_payload(tmp_path: Path):
    tr = QnaTransformer()
    doc_dict = make_parsed_document(
        uri="file:///data/qna.tsv",
        rows=[{"id": "1", "question": "Q1", "answer": "A1", "published": "Y", "user_id": "u1"}],
    ).model_dump(mode="json")

    p = tmp_path / "parsed_list.json"
    p.write_text(json.dumps([doc_dict], ensure_ascii=False), encoding="utf-8")

    docs = list(tr.read_parsed_document(str(p)))
    assert len(docs) == 1
    assert isinstance(docs[0], ParsedDocument)
    assert docs[0].source.file_type == FileType.tsv
    assert docs[0].collection == TEST_COLLECTION


def test_read_parsed_document_from_dict_with_data_list(tmp_path: Path):
    tr = QnaTransformer()
    doc_dict = make_parsed_document(
        uri="file:///data/qna.tsv",
        rows=[{"id": "2", "question": "Q2", "answer": "A2", "published": "N", "user_id": "u2"}],
    ).model_dump(mode="json")

    p = tmp_path / "parsed_dict_data.json"
    p.write_text(json.dumps({"data": [doc_dict]}, ensure_ascii=False), encoding="utf-8")

    docs = list(tr.read_parsed_document(str(p)))
    assert len(docs) == 1
    assert docs[0].blocks[0].meta["id"] == "2"


def test_read_parsed_document_from_single_dict(tmp_path: Path):
    tr = QnaTransformer()
    doc_dict = make_parsed_document(
        uri="file:///data/qna.tsv",
        rows=[{"id": "3", "question": "Q3", "answer": "A3", "published": "Y", "user_id": "u3"}],
    ).model_dump(mode="json")

    p = tmp_path / "parsed_single.json"
    p.write_text(json.dumps(doc_dict, ensure_ascii=False), encoding="utf-8")

    docs = list(tr.read_parsed_document(str(p)))
    assert len(docs) == 1
    assert docs[0].blocks[0].meta["question"] == "Q3"


def test_read_parsed_document_unsupported_format_raises(tmp_path: Path):
    tr = QnaTransformer()
    p = tmp_path / "bad.json"
    p.write_text('"just a string, not an object/list"', encoding="utf-8")

    with pytest.raises(ValueError):
        _ = list(tr.read_parsed_document(str(p)))


# ---------------------------
# transform()
# ---------------------------
def test_transform_maps_rows_to_chunks(monkeypatch):
    tr = QnaTransformer(default_source_id="tsv")

    # infer_date_from_path를 고정된 값으로 패치
    fixed_dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "api_server.app.adapters.transformers.qna_transformer.infer_date_from_path",
        lambda uri: fixed_dt,
        raising=True,
    )

    pd = make_parsed_document(
        uri="file:///data/day_3/qna.tsv",
        rows=[
            {"id": "10", "question": "지구 반경?", "answer": "약 6371km", "published": "Y", "user_id": "alice"},
            {"id": "11", "question": "빛의 속도?", "answer": "299792458", "published": "N", "user_id": "bob"},
        ],
    )

    chunks = list(tr.transform([pd]))
    assert len(chunks) == 2
    for c in chunks:
        assert isinstance(c, NormalizedChunk)
        # 날짜/공통 메타
        assert c.created_date == fixed_dt and c.updated_date == fixed_dt
        assert c.source_path == "file:///data/day_3/qna.tsv"
        assert c.file_type == FileType.tsv
        assert c.collection == TEST_COLLECTION
        # source_id 규칙: default_source_id + "_" + id
        assert c.source_id in {"tsv_10", "tsv_11"}

    c0 = next(c for c in chunks if c.source_id == "tsv_10")
    assert c0.question == "지구 반경?"
    assert c0.answer == "약 6371km"
    assert c0.author == "alice"
    assert c0.published is True

    c1 = next(c for c in chunks if c.source_id == "tsv_11")
    assert c1.question == "빛의 속도?"
    assert c1.answer == "299792458"
    assert c1.author == "bob"
    assert c1.published is False


def test_transform_skips_non_row_blocks(monkeypatch):
    tr = QnaTransformer()
    monkeypatch.setattr(
        "api_server.app.adapters.transformers.qna_transformer.infer_date_from_path",
        lambda uri: datetime(2025, 9, 22, tzinfo=timezone.utc),
        raising=True,
    )

    # row 1개 + body 1개 → body는 무시
    pd = ParsedDocument(
        source=SourceRef(uri="file:///d/qna.tsv", file_type=FileType.tsv),
        title=None,
        blocks=[
            ParsedBlock(type="row", text=None, meta={"id": "1", "question": "Q", "answer": "A", "published": "Y", "user_id": "u"}),
            ParsedBlock(type="row", text=None, meta={"id": "2", "question": "Q2", "answer": "A2", "published": "Y", "user_id": "u2"}),
            ParsedBlock(type="body", text="본문 텍스트", meta={}),
        ],
        lang=None,
        meta={},
        collection=TEST_COLLECTION,
    )

    chunks = list(tr.transform([pd]))
    assert len(chunks) == 2
    assert chunks[0].source_id == "tsv_1"


def test_transform_defaults_when_missing_fields(monkeypatch):
    tr = QnaTransformer()
    monkeypatch.setattr(
        "api_server.app.adapters.transformers.qna_transformer.infer_date_from_path",
        lambda uri: datetime(2022, 5, 5, tzinfo=timezone.utc),
        raising=True,
    )

    # answer, user_id, published 누락 → answer="", author=None, published=False(빈 문자열은 startswith('Y')가 False)
    pd = make_parsed_document(
        uri="file:///data/qna.tsv",
        rows=[
            {"id": "99", "question": None, "answer": None, "user_id": None},  # published 없음
        ],
    )

    chunks = list(tr.transform([pd]))
    assert len(chunks) == 1
    c = chunks[0]
    assert c.source_id == "tsv_99"
    assert c.question is None
    assert c.answer == ""          # 기본값
    assert c.author is None
    assert c.published is False    # "":upper().startswith("Y") → False
