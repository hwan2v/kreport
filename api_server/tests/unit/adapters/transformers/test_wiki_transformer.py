# api_server/tests/unit/adapters/transformers/test_wiki_transformer.py

from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from api_server.app.adapters.transformers.wiki_transformer import WikiTransformer
from api_server.app.domain.models import (
    ParsedDocument,
    ParsedBlock,
    SourceRef,
    FileType,
    Collection,
    NormalizedChunk,
)

# Collection enum이 있다면 일반적으로 Collection.wiki / Collection.qna 같은 멤버가 있을 것이라 가정
TEST_COLLECTION = getattr(Collection, "wiki", None) or getattr(Collection, "qna", None)


def make_parsed_doc(
    *,
    uri: str = "file:///data/day_3/wiki.html",
    title: str = "문서제목",
    body="본문 12.3% 텍스트",
    summary="요약 5.0%",
    infobox="회사: 카카오뱅크 (100.0%)",
    paragraph="문단 0.5%",
    file_type: FileType = FileType.html,
    collection=TEST_COLLECTION,
):
    blocks = [
        ParsedBlock(type="body", text=body, meta={}),
        ParsedBlock(type="summary", text=summary, meta={}),
        ParsedBlock(type="infobox", text=infobox, meta={}),
        ParsedBlock(type="paragraph", text=paragraph, meta={}),
    ]
    return ParsedDocument(
        source=SourceRef(uri=uri, file_type=file_type),
        title=title,
        blocks=blocks,
        lang="ko",
        meta={},
        collection=collection,
    )


def test_read_parsed_document_reads_jsonl(tmp_path: Path):
    """
    wiki json 파일을 읽어 ParsedDocument로 변환하는 메서드.
    """

    tr = WikiTransformer()

    d1 = make_parsed_doc(title="A").model_dump(mode="json")
    d2 = make_parsed_doc(title="B").model_dump(mode="json")

    p = tmp_path / "docs.jsonl"
    p.write_text(json.dumps(d1, ensure_ascii=False) + "\n" + json.dumps(d2, ensure_ascii=False) + "\n", encoding="utf-8")

    docs = list(tr.read_parsed_document(str(p)))
    assert len(docs) == 2
    assert isinstance(docs[0], ParsedDocument)
    assert docs[0].title == "A"
    assert docs[1].title == "B"
    assert docs[0].source.file_type == FileType.html


def test_read_parsed_document_ignores_empty_lines(tmp_path: Path):
    """
    wiki json 파일을 읽어 ParsedDocument로 변환하는 메서드.
    공백 라인을 무시하고 ParsedDocument를 올바르게 읽어오는지 확인.
    """

    tr = WikiTransformer()
    d1 = make_parsed_doc(title="OnlyOne").model_dump(mode="json")
    p = tmp_path / "docs.jsonl"
    p.write_text("\n" + json.dumps(d1, ensure_ascii=False) + "\n\n", encoding="utf-8")

    docs = list(tr.read_parsed_document(str(p)))
    assert len(docs) == 1
    assert docs[0].title == "OnlyOne"


def test_normalize_percentage_formats_to_two_decimals():
    """
    퍼센트 포맷을 소수점 둘째 자리까지 포맷하는 메서드.
    """

    tr = WikiTransformer()
    text = "성장률 3.1% / 점유율 25.0% / 오류율 0.0%"
    norm = tr._normalize_percentage(text)
    assert "3.10%" in norm
    assert "25.00%" in norm
    assert "0.00%" in norm


def test_transform_builds_chunk_and_normalizes_percentages(monkeypatch):
    """
    퍼센트 포맷을 소수점 둘째 자리까지 포맷하는 메서드.
    """

    tr = WikiTransformer(default_author=None, default_published=True, default_source_id="html")

    fixed_dt = datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "api_server.app.adapters.transformers.wiki_transformer.infer_date_from_path",
        lambda uri: fixed_dt,
        raising=True,
    )

    doc = make_parsed_doc(
        title="카카오뱅크",
        body="본문에 12.3% 가 포함됩니다.",
        summary="요약 5.0% 텍스트",
        infobox="정보 100.0%",
        paragraph="문단 0.5%",
    )

    chunks = list(tr.transform([doc]))
    assert len(chunks) == 1
    c = chunks[0]
    assert isinstance(c, NormalizedChunk)

    # 기본 메타
    assert c.source_id == "html_0"          # 증가 번호
    assert c.source_path == doc.source.uri
    assert c.collection == TEST_COLLECTION
    # file_type은 구현상 "html" 문자열을 사용 -> 타입이 Enum이 아닐 수도 있으므로 값만 간접 확인
    assert str(c.file_type).lower().endswith("html")

    # 날짜/작성자/공개여부
    assert c.created_date == fixed_dt and c.updated_date == fixed_dt
    assert c.author is None
    assert c.published is True

    # 본문/요약/인포/문단이 모두 퍼센트 포맷으로 정규화
    assert "12.30%" in (c.body or "")
    assert "5.00%" in (c.summary or "")
    assert "100.00%" in (c.infobox or "")
    assert "0.50%" in (c.paragraph or "")

    # features는 스케일된 값(0~1)이며 주요 키가 포함되어야 한다
    for k in ("body", "summary", "infobox", "paragraph"):
        assert k in c.features
        assert 0.0 <= c.features[k] <= 1.0


def test_transform_multiple_docs_feature_scaling_and_ids(monkeypatch):
    """
    여러 문서 입력 시 source_id가 html_0, html_1처럼 증가하는지.
    """
    tr = WikiTransformer(default_source_id="html")

    fixed_dt = datetime(2023, 9, 9, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "api_server.app.adapters.transformers.wiki_transformer.infer_date_from_path",
        lambda uri: fixed_dt,
        raising=True,
    )

    doc_short = make_parsed_doc(title="짧은", body="짧다 1.0%", summary="S", infobox="I", paragraph="P")
    doc_long = make_parsed_doc(title="긴문서", body=("매우 " * 100) + "2.5%", summary=("요약 " * 30), infobox=("정보 " * 15), paragraph=("문단 " * 10))

    chunks = list(tr.transform([doc_short, doc_long]))
    assert {c.source_id for c in chunks} == {"html_0", "html_1"}

    c_short = next(c for c in chunks if c.title == "짧은")
    c_long = next(c for c in chunks if c.title == "긴문서")

    # created/updated 동일, 고정된 시간
    for c in (c_short, c_long):
        assert c.created_date == fixed_dt and c.updated_date == fixed_dt

    # 길이가 더 긴 문서는 feature 스케일링상 body 점수가 더 크거나 같아야 함
    assert c_long.features["body"] >= c_short.features["body"]
    # 모든 feature 키 존재, [0,1] 범위
    for c in (c_short, c_long):
        for k in ("body", "summary", "infobox", "paragraph"):
            assert 0.0 <= c.features[k] <= 1.0
