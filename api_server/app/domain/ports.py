"""
도메인 포트(추상 인터페이스).

애플리케이션 서비스(유스케이스)는 아래 포트들(추상)에만 의존합니다.
구체 구현은 infra 레이어에서 제공하고, FastAPI DI로 주입합니다.
"""

from __future__ import annotations

from typing import Protocol, Iterable, List
from datetime import datetime, timedelta
from .models import (
    RawDocument,
    ParsedDocument,
    NormalizedChunk,
    Collection,
    IndexResult,
)

class ListenPort(Protocol):
    """원문을 가져온다(HTTP, 파일, S3 등)."""
    def listen(self, source: str, date: str, extension: str) -> List[str]:
        """
        Returns:
            List[str]: 파일 경로 목록
        """
        ...

class FetchPort(Protocol):
    """원본으로부터 문서를 가져온다(HTTP, 파일, S3 등)."""

    def fetch(self, uri: str, collection: Collection) -> RawDocument:
        """
        Args:
            uri: 'https://...', 'file:///...', 's3://bucket/key' 등
        Returns:
            RawDocument: 원문(텍스트/바이트, 인코딩/메타 포함)
        """
        ...


class ParsePort(Protocol):
    """원문을 구조화된 문서로 파싱(HTML → 블록들)."""

    def parse(self, raw: RawDocument) -> ParsedDocument:
        """
        Args:
            raw: fetch 단계 산출물
        Returns:
            ParsedDocument: 블록/타이틀/언어/메타가 채워진 구조화 결과
        """
        ...


class TransformPort(Protocol):
    """
    파싱 결과를 인덱싱 단위 청크로 정규화/변환.
    - 문단/문장 단위 청킹
    - 텍스트 정제(공백/HTML 제거 등)
    - (옵션) 언어 감지, 토큰 카운트, 임베딩 생성 등
    """
    def transform(self, doc: ParsedDocument) -> Iterable[NormalizedChunk]:
        """
        Returns:
            Iterable[NormalizedChunk]: OpenSearch 적재 가능한 청크 스트림
        """
        ...
    
    def read_parsed_document(self, resource_file_path: str) -> Iterable[ParsedDocument]:
        """
        Returns:
            Iterable[ParsedDocument]: 파싱 결과
        """
        ...


class IndexPort(Protocol):
    """
    청크들을 타겟 인덱스/컬렉션에 적재.
    기본은 OpenSearch bulk index를 상정.
    """

    def index(self, chunks: Iterable[NormalizedChunk]) -> IndexResult:
        """
        Returns:
            IndexResult: 성공/실패 건수 및 실패 상세
        """
        ...

class SearchPort(Protocol):
    """
    검색을 수행합니다.
    """
    def search(self, query: str, size: int = 3) -> Any:
        """
        Returns:
            Any: 검색 결과
        """
        ...
