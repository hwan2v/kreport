# app/domain/services/search_service.py
"""
SearchService
==============

문서 파이프라인 오케스트레이터.

Flow:
    Fetcher → Parser → Transformer → Indexer

- 도메인은 **Port(인터페이스)** 에만 의존합니다. (DIP)
- 구현체는 adapters 레이어에서 주입(의존성 주입; DI)합니다.

예시:
    svc = SearchService(fetcher, parser, transformer, indexer)
    result = svc.run(source="https://example.com", collection="news")
    # 또는 여러 소스를 한 번에 bulk 색인:
    result = svc.many(sources=[...], collection="news")
"""

from __future__ import annotations
from pydantic import BaseModel
from pathlib import Path
import json
import os
from typing import Iterable, Sequence, List

import logging
import traceback

from api_server.app.domain.ports import (
    FetchPort, ParsePort, TransformPort, IndexPort, ListenPort
)
from api_server.app.domain.models import (
    IndexResult,
    IndexErrorItem,
    NormalizedChunk,
    ParsedDocument,
    RawDocument,
)

logger = logging.getLogger(__name__)


class IndexService:
    """문서를 가져와 parse 수행하는 유스케이스 서비스."""

    def __init__(
        self,
        listener: ListenPort,
        fetcher: FetchPort,
        parser: ParsePort,
        transformer: TransformPort,
        indexer: IndexPort
    ) -> None:
        """
        Args:
            fetcher: 원문을 가져오는 포트(HTTP/파일/S3 등)
            parser: 원문을 구조화 문서로 파싱
        """
        self._listener = listener
        self._fetcher = fetcher
        self._parser = parser
        self._transformer = transformer
        self._indexer = indexer
        
    # ---------- public API ----------

    def extract(self, source: str, date: str, collection: Collection) -> [ParsedDocument]:
        """단일 소스를 처리해 즉시 파싱합니다.

        Args:
            source: 처리 대상(예: html, tsv)
            date: 날짜
            collection: 컬렉션

        Returns:
            ParsedDocument: 파싱 결과
        """
        logger.info("service.run: source=%s date=%s", source, date)
        
        result = []
        resource_files = self._listener.listen(source, date)
        for resource_file in resource_files:
            raw: RawDocument = self._fetcher.fetch(resource_file, collection)
            parsed: ParsedDocument = self._parser.parse(raw)
            result.append(parsed)
        return self._save_parsed_document(
            collection, date, docs=result, suffix="parsed")

    def transform(self, source: str, date: str, collection: Collection) -> [NormalizedChunk]:
        """단일 소스를 처리해 즉시 변환합니다.
        """
        logger.info("service.transform: source=%s date=%s", source, date)
        
        parsed_file_name = self._create_file_name(collection, date, suffix="parsed")
        parsed_docs: List[ParsedDocument] = self._transformer.read_parsed_document(parsed_file_name)
        result = self._transformer.transform(parsed_docs)
        return self._save_parsed_document(
            collection, date, docs=result, suffix="normalized")

    def index(self, source: str, date: str, collection: Collection) -> None:
        """단일 소스를 처리해 즉시 인덱싱합니다.
        """
        logger.info("service.index: source=%s date=%s", source, date)
        
        index_name = self._indexer.create_index(source, date)
        normalized_file_name = self._create_file_name(collection, date, suffix="normalized")
        print(normalized_file_name)
        result = self._indexer.index(index_name, normalized_file_name)
        print(result)
        return self._indexer.rotate_alias_to_latest(
            self._indexer.alias_name, 
            self._indexer.prefix_index_name, 
            delete_old=False
        )

    #================= internal helpers =================
    def _save_parsed_document(
        self, 
        collection: Collection, 
        date: str, 
        docs: List[BaseModel] = None, 
        suffix: str = "normalized",
        out_dir: str = "./data"
    ):
        # JSON 직렬화
        file_name = self._create_file_name(collection, date, suffix, out_dir)
        out = Path(file_name)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False) + "\n")
        print(f"{file_name} 파일이 생성되었습니다.")
        return out.name
    
    def _create_file_name(
        self, 
        collection: Collection, 
        date: str, 
        suffix: str = "normalized",
        out_dir: str = "./data"
    ) -> str:
        file_name = f"{collection.value}_{date}_{suffix}.json"
        return f'{out_dir}/{file_name}'