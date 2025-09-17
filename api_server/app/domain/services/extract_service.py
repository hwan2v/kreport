# app/domain/services/extract_service.py
"""
ExtractService
==============

문서 파이프라인 오케스트레이터.

Flow:
    Fetcher → Parser → Transformer → Indexer

- 도메인은 **Port(인터페이스)** 에만 의존합니다. (DIP)
- 구현체는 adapters 레이어에서 주입(의존성 주입; DI)합니다.

예시:
    svc = ExtractService(fetcher, parser, transformer, indexer)
    result = svc.run(source="https://example.com", collection="news")
    # 또는 여러 소스를 한 번에 bulk 색인:
    result = svc.run_many(sources=[...], collection="news")
"""

from __future__ import annotations

from typing import Iterable, Sequence
import logging

from app.domain.ports import FetchPort, ParsePort, TransformPort, IndexPort
from app.domain.models import (
    IndexResult,
    IndexErrorItem,
    NormalizedChunk,
    ParsedDocument,
    RawDocument,
)

logger = logging.getLogger(__name__)


class ExtractService:
    """문서를 가져와(parse/transform) 인덱싱까지 수행하는 유스케이스 서비스."""

    def __init__(
        self,
        fetcher: FetchPort,
        parser: ParsePort,
        transformer: TransformPort,
        indexer: IndexPort,
    ) -> None:
        """
        Args:
            fetcher: 원문을 가져오는 포트(HTTP/파일/S3 등)
            parser: 원문을 구조화 문서로 파싱
            transformer: 파싱 결과를 인덱싱 단위 청크로 변환
            indexer: 청크를 타겟(OpenSearch 등)에 적재
        """
        self._fetcher = fetcher
        self._parser = parser
        self._transformer = transformer
        self._indexer = indexer

    # ---------- public API ----------

    def run(self, source: str, collection: str) -> IndexResult:
        """단일 소스를 처리해 즉시 인덱싱합니다.

        Args:
            source: 처리 대상(예: URL, file:// 경로)
            collection: 컬렉션 이름(파티션/네임스페이스)

        Returns:
            IndexResult: 적재 성공 수/에러 목록
        """
        logger.info("extract.run: source=%s collection=%s", source, collection)
        chunks = self._iter_chunks_for_single(source, collection)
        return self._indexer.index(chunks)

    def run_many(self, sources: Sequence[str], collection: str) -> IndexResult:
        """여러 소스를 한 번의 bulk로 처리합니다. (권장; 성능 ↑)

        Args:
            sources: 처리 대상들의 목록
            collection: 컬렉션 이름

        Returns:
            IndexResult: 전체 적재 결과 합산
        """
        logger.info("extract.run_many: count=%d collection=%s", len(sources), collection)
        chunks = self._iter_chunks_for_many(sources, collection)
        return self._indexer.index(chunks)

    # ---------- internal helpers ----------

    def _iter_chunks_for_single(self, source: str, collection: str) -> Iterable[NormalizedChunk]:
        """단일 소스 → 청크 스트림 생성(지연 평가)."""
        raw: RawDocument = self._fetcher.fetch(source)
        parsed: ParsedDocument = self._parser.parse(raw)
        yield from self._transformer.to_chunks(parsed, collection)

    def _iter_chunks_for_many(self, sources: Sequence[str], collection: str) -> Iterable[NormalizedChunk]:
        """여러 소스 → 청크 스트림 생성(메모리 사용 최소화)."""
        for src in sources:
            try:
                yield from self._iter_chunks_for_single(src, collection)
            except Exception as exc:  # 실패한 소스는 건너뛰고 계속 진행
                logger.exception("extract: failed source=%s", src)
                # 인덱서가 에러 수집을 못 하는 경우를 대비해, 필요하면
                # 여기서 에러용 '메타 청크'를 만들어 기록하는 전략도 가능.
                continue
