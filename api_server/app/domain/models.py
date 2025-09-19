"""
도메인 모델 정의.

- RawDocument: 페치된 원문(HTML/텍스트/마크다운 등)
- ParsedDocument/ParsedBlock: 파서가 구조화한 결과
- NormalizedChunk: 인덱싱 단위(컬렉션에 적재될 “정규화된 청크”)
- IndexResult: 인덱싱 결과 요약

Pydantic v2 기반 모델이라 검증/직렬화가 용이합니다.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


JSONDict = dict[str, Any]

class Collection(str, Enum):
    wiki = "wiki"
    qna = "qna"

class FileType(str, Enum):
    """원문 콘텐츠 타입."""
    html = "html"
    tsv = "tsv"

class SourceRef(BaseModel):
    """원본 리소스 식별자/메타데이터."""
    uri: str = Field(..., description="원본 식별자(URL, file://, s3:// 등)")
    file_type: FileType | None = Field(
        None, description="알고 있을 경우 명시(미지정이면 페처/파서가 추정)"
    )
    headers: dict[str, str] | None = Field(
        default=None, description="페칭 시 사용한 헤더(재현성/감사 용도)"
    )


class RawDocument(BaseModel):
    """페치 단계의 결과(바이트/텍스트 원문)."""
    source: SourceRef
    body_text: str | None = Field(
        None, description="텍스트로 디코딩한 본문(HTML/MD/TXT 등)"
    )
    encoding: str | None = Field(None, description="디코딩에 사용한 문자셋")
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    collection: Collection | None = Field(None, description="컬렉션 이름")


class ParsedBlock(BaseModel):
    """파서가 뽑아낸 최소 블록 단위."""
    type: Literal["title", "paragraph", "code", "list", "image", "other", "row"] = Field(
        "paragraph", description="블록 유형"
    )
    text: str | None = Field(None, description="텍스트 콘텐츠(이미지 등은 None)")
    meta: JSONDict = Field(default_factory=dict, description="태그/속성 등 부가 정보")   


class ParsedDocument(BaseModel):
    """구조화된 문서(여러 블록으로 구성)."""
    source: SourceRef
    title: str | None = Field(None, description="문서 제목 추정")
    blocks: list[ParsedBlock] = Field(default_factory=list)
    lang: str | None = Field(None, description="BCP-47 (예: ko, en-US)")
    meta: JSONDict = Field(default_factory=dict, description="추출 시점의 부가 메타")
    collection: Collection | None = Field(None, description="컬렉션 이름")


class NormalizedChunk(BaseModel):
    """
    인덱싱 대상 문서 1건과 1:1로 매핑되는 모델.
    OpenSearch 매핑 예시:
      - source_id: keyword
      - source_path: text (+ keyword 서브필드 권장)
      - file_type: keyword
      - title: text (+ keyword 서브필드 권장)
      - body: text
      - title_embedding: knn_vector
      - body_embedding: knn_vector
      - created_date/updated_date: date
      - author: keyword
      - is_open: boolean
    """

    # ---- 식별/메타 ----
    source_id: str = Field(..., description="원본(수집원) 식별자")
    source_path: str = Field(..., description="원본 경로(URL/파일 경로 등)")
    file_type: str = Field(..., description="원본 유형(e.g. html, pdf, tsv, md)")
    collection: str = Field(..., description="컬렉션 이름")

    # ---- 내용 ----
    title: str | None = Field(None, description="문서 제목")
    body: str = Field(..., description="본문 텍스트(정규화/전처리 후)")

    # ---- 임베딩(옵션) ----
    title_embedding: list[float] | None = Field(
        default=None, description="제목 임베딩 벡터(모델 차원과 일치해야 함)"
    )
    body_embedding: list[float] | None = Field(
        default=None, description="본문 임베딩 벡터(모델 차원과 일치해야 함)"
    )

    # ---- 시간/작성/공개 ----
    created_date: datetime = Field(..., description="문서 생성 시간(원본 기준 또는 파이프라인 정책)")
    updated_date: datetime = Field(..., description="문서 갱신 시간(원본 기준 또는 파이프라인 정책)")
    author: str | None = Field(None, description="작성자(정확 매칭/집계용)")
    is_open: bool = Field(True, description="공개 여부")


class NormalizedChunk2(BaseModel):
    """
    인덱싱 단위 청크.
    - 컬렉션/문서/시퀀스 기준으로 문서를 “쪼갠” 레코드
    - OpenSearch 문서 1건에 해당
    """
    collection: str = Field(..., description="컬렉션 이름(논리 파티션 키)")
    doc_id: str = Field(..., description="원문 문서 식별자(URI 해시 등)")
    seq: int = Field(..., ge=0, description="문서 내 청크 순번(0부터)")
    title: str | None = Field(None, description="문서/청크 타이틀")
    content: str = Field(..., description="검색/색인 대상 본문")
    url: HttpUrl | None = Field(None, description="원문 접근 URL(있다면)")
    lang: str | None = Field(None, description="언어 코드")
    meta: JSONDict = Field(default_factory=dict, description="추가 메타(작성자/태그 등)")
    # 선택: 임베딩 사용 시
    embedding: list[float] | None = Field(
        default=None, description="벡터 검색을 쓸 때만 채움"
    )


class IndexErrorItem(BaseModel):
    """인덱싱 실패 항목 요약."""
    doc_id: str
    seq: int
    reason: str


class IndexResult(BaseModel):
    """인덱싱 실행 결과."""
    indexed: int = Field(..., ge=0)
    errors: list[IndexErrorItem] = Field(default_factory=list)
