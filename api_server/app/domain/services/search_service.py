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

import os
from typing import Iterable, Sequence, List
import logging
import traceback

from api_server.app.domain.ports import FetchPort, ParsePort, TransformPort, IndexPort, SearcherPort, ListenPort
from api_server.app.domain.models import (
    IndexResult,
    IndexErrorItem,
    NormalizedChunk,
    ParsedDocument,
    RawDocument,
)

logger = logging.getLogger(__name__)


class SearchService:
    """문서를 가져와 parse 수행하는 유스케이스 서비스."""

    def __init__(
        self,
        listener: ListenPort,
        fetcher: FetchPort,
        parser: ParsePort,
        transformer: TransformPort,
        indexer: IndexPort,
        searcher: SearcherPort,
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
        self._searcher = searcher
        
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
            result.append(parsedDocument)
        return self._save_parsed_document(collection, date, docs=result)

    
    def parse(self, source: str, date: str, collection: Collection) -> [ParsedDocument]:
        """단일 소스를 처리해 즉시 파싱합니다.
        """
        logger.info("service.parse: source=%s date=%s", source, date)
        file_name = f'{source}_{date}'
        resource_dir_path = self._create_resource_dir_path(source, date)
        result = []
        for filename in os.listdir(resource_dir_path):
            source_file = f'{resource_dir_path}/{filename}'
            print(source_file)
            parsedDocument = self._iter_chunks_for_single(source_file, file_name)
            result.append(parsedDocument)
        return self._save_parsed_document(collection, date, docs=result)

    def transform(self, source: str, date: str) -> [NormalizedChunk]:
        """단일 소스를 처리해 즉시 변환합니다.
        """
        logger.info("service.transform: source=%s date=%s", source, date)
        collection = f'{source}_{date}'
        resource_file_path = f'./data/{collection}.json'
        result = self._transformer.transform(resource_file_path)
        collection = f'{source}_{date}_normalized'
        return self._save_parsed_document(collection, date, docs=result)

    def index(self, source: str, date: str) -> None:
        """단일 소스를 처리해 즉시 인덱싱합니다.
        """
        logger.info("service.index: source=%s date=%s", source, date)
        collection = f'{source}_{date}_normalized'
        index_name = self._indexer.create_index(source, date)
        resource_file_path = f'./data/{source}_{date}_normalized.json'
        self._indexer.index(index_name, resource_file_path)
        alias_name = self._indexer.get_alias_name(index_name)
        self._indexer.alias_index(alias_name, date)
        return alias_name
    
    def search(self, query: str, size: int = 3) -> [NormalizedChunk]:
        """검색을 수행합니다.
        """
        # todo. fix alias_name
        alias_name = 'tsv'
        result = self._searcher.search(alias_name, query, size)
        return result

    #================= internal helpers =================
    def _save_parsed_document(
        self, 
        collection: str, 
        date: str, 
        docs: List[BaseModel] = None, 
        out_dir: str = "./data"
    ):
        # JSON 직렬화
        file_name = f"{collection}_{date}.json"
        out = Path(out_dir) / file_name
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False) + "\n")
        print(f"{file_name} 파일이 생성되었습니다.")
        return out.name