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

import os
from typing import Iterable, Sequence
import logging

from api_server.app.domain.ports import FetchPort, ParsePort, TransformPort, IndexPort
from api_server.app.domain.models import (
    IndexResult,
    IndexErrorItem,
    NormalizedChunk,
    ParsedDocument,
    RawDocument,
)

logger = logging.getLogger(__name__)


class ExtractService:
    """문서를 가져와 parse 수행하는 유스케이스 서비스."""

    def __init__(
        self,
        fetcher: FetchPort,
        parser: ParsePort
    ) -> None:
        """
        Args:
            fetcher: 원문을 가져오는 포트(HTTP/파일/S3 등)
            parser: 원문을 구조화 문서로 파싱
        """
        self._fetcher = fetcher
        self._parser = parser

    # ---------- public API ----------

    def run(self, source: str, date: str) -> ParsedDocument:
        """단일 소스를 처리해 즉시 파싱합니다.

        Args:
            source: 처리 대상(예: html, tsv)
            date: 날짜

        Returns:
            ParsedDocument: 파싱 결과
        """
        logger.info("extract.run: source=%s date=%s", source, date)
        collection = f'{source}_{date}'
        resource_dir_path = self._create_resource_dir_path(source, date)
        result = []
        for source_file in os.listdir(resource_dir_path):
            print(source_file)
            chunks = self._iter_chunks_for_single(source_file, collection)
            result.append(chunks)
        return self._parser.parse(result)

    def run_many(self, sources: Sequence[str], date: str) -> ParsedDocument:
        """여러 소스를 한 번의 bulk로 처리합니다. (권장; 성능 ↑)

        Args:
            sources: 처리 대상들의 목록
            date: 날짜

        Returns:
            ParsedDocument: 파싱 결과
        """
        logger.info("extract.run_many: count=%d date=%s", len(sources), date)
        for source in sources:
            collection = f'{source}_{date}'
            resource_dir_path = self._create_resource_dir_path(source, date)
            source_files = os.listdir(resource_dir_path)
            chunks = self._iter_chunks_for_many(source_files, date)
        return self._parser.parse(chunks)

    # ---------- internal helpers ----------
    
    def _create_resource_dir_path(self, source: str, date: str) -> str:
        return f"api_server/resources/data/{source}/day_{date}"

    def _iter_chunks_for_single(self, source_file: str, collection: str) -> Iterable[NormalizedChunk]:
        """단일 소스 → 청크 스트림 생성(지연 평가)."""
        raw: RawDocument = self._fetcher.fetch(source_file)
        parsed: ParsedDocument = self._parser.parse(raw)
        yield from self._transformer.to_chunks(parsed, collection)

    def _iter_chunks_for_many(self, source_files: Sequence[str], collection: str) -> Iterable[NormalizedChunk]:
        """여러 소스 → 청크 스트림 생성(메모리 사용 최소화)."""
        for src in source_files:
            try:
                yield from self._iter_chunks_for_single(src, collection)
            except Exception as exc:  # 실패한 소스는 건너뛰고 계속 진행
                logger.exception("extract: failed source=%s", src)
                # 인덱서가 에러 수집을 못 하는 경우를 대비해, 필요하면
                # 여기서 에러용 '메타 청크'를 만들어 기록하는 전략도 가능.
                continue
