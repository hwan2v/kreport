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
import logging
import traceback
from typing import List

from api_server.app.domain.ports import (
    FetchPort, ParsePort, TransformPort, IndexPort, ListenPort
)
from api_server.app.domain.models import (
    NormalizedChunk,
    ParsedDocument,
    RawDocument,
    IndexResult,
    AliasResult
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
        indexer: IndexPort,
        input_base_dir: str = "api_server/resources/data"
    ) -> None:
        """
        인덱스 서비스 초기화.
        Args:
            listener: ListenPort      : 수집 파일 리스트 조회
            fetcher: FetchPort        : 수집 파일 조회
            parser: ParsePort         : 수집 파일 파싱
            transformer: TransformPort: 파싱 파일 변환
            indexer: IndexPort        : 변환 파일 색인
            input_base_dir: str       : 수집 파일 기본 경로
        """
        self._listener = listener
        self._fetcher = fetcher
        self._parser = parser
        self._transformer = transformer
        self._indexer = indexer
        self._input_base_dir = input_base_dir
        
    # ================= public API =================

    def extract(
        self, 
        source: str, 
        date: str, 
        collection: Collection) -> str:
        """
        수집된 문서를 파싱하여 저장하는 메서드.

        Args:
            source: 처리 대상(예: html, tsv)
            date: 날짜
            collection: 컬렉션

        Returns:
            str: 파싱 결과의 파일 이름
        """
        logger.info("service.run: source=%s date=%s", source, date)
        
        result = []
        print(f"self._input_base_dir: {self._input_base_dir}")
        resource_files = self._listener.listen(
            source, date, 
            extension=source.lower(), 
            base_dir=self._input_base_dir)
        print(f"resource_files: {resource_files}")
        for resource_file in resource_files:
            raw: RawDocument = self._fetcher.fetch(resource_file, collection)
            parsed: ParsedDocument = self._parser.parse(raw)
            result.append(parsed)

        out_dir = self._get_resource_dir_path(source, date)
        return self._save_parsed_document(
            collection, 
            date, 
            docs=result, 
            suffix="parsed", 
            out_dir=out_dir)

    def transform(
        self, 
        source: str, 
        date: str, 
        collection: Collection) -> str:
        """
        파싱된 문서를 색인 문서 형태로 변환하여 파일로 저장하는 메서드.
        Args:
            source: str
            date: str
            collection: Collection
        Returns:
            str: 변환된 문서의 파일 이름
        """
        logger.info("service.transform: source=%s date=%s", source, date)
        
        # 파싱 문서 읽기기
        out_dir = self._get_resource_dir_path(source, date)
        parsed_file_name = self._create_file_name(
            collection, 
            date, 
            suffix="parsed", 
            out_dir=out_dir)
        parsed_docs: List[ParsedDocument] = \
            self._transformer.read_parsed_document(parsed_file_name)

        # 변환
        result = self._transformer.transform(parsed_docs)
        return self._save_parsed_document(
            collection, 
            date, 
            docs=result, 
            suffix="normalized", 
            out_dir=out_dir)

    def index(self, source: str, date: str, collection: Collection) -> Dict[str, Any]:
        """
        변환된 문서를 색인하는 메서드.
        Args:
            source: str
            date: str
            collection: Collection
        Returns:
            Dict[str, Any]: 색인 결과
        """
        logger.info("service.index: source=%s date=%s", source, date)
        
        # 변환된 문서 읽기
        out_dir = self._get_resource_dir_path(source, date)
        normalized_file_name = self._create_file_name(
            collection, 
            date, 
            suffix="normalized", 
            out_dir=out_dir)
        # 인덱스 생성
        index_name = self._indexer.create_index(source, date)
        
        # 인덱싱
        indexResult: IndexResult = self._indexer.index(index_name, normalized_file_name)

        # 두 인덱스 결과 병합(별칭 추가)
        aliasResult: AliasResult = self._indexer.rotate_alias_to_latest(
            self._indexer.alias_name, 
            self._indexer.prefix_name, 
            delete_old=False
        )
        result = indexResult.model_dump() | aliasResult.model_dump()
        return result

    #================= internal helpers =================
    def _get_resource_dir_path(self, source: str, date: str) -> str:
        return f"api_server/resources/data/{source}/day_{date}"
    
    def _save_parsed_document(
        self, 
        collection: Collection, 
        date: str, 
        docs: List[BaseModel] = None, 
        suffix: str = "normalized",
        out_dir: str = "./data"
    ) -> str:
        """
        파일 저장하는 메서드.
        Args:
            collection: Collection
            date: str
            docs: List[BaseModel]
            suffix: str
            out_dir: str
        Returns:
            str: 저장된 파일 이름
        """
        file_name = self._create_file_name(collection, date, suffix, out_dir)
        out = Path(file_name)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(
                    doc.model_dump(mode="json"), ensure_ascii=False))
                f.write("\n")
        print(f"{file_name} 파일이 생성되었습니다.")
        return out.name
    
    def _create_file_name(
        self, 
        collection: Collection, 
        date: str, 
        suffix: str = "normalized",
        out_dir: str = "./data"
    ) -> str:
        """
        파일 이름 생성하는 메서드.
        Args:
            collection: Collection
            date: str
            suffix: str
            out_dir: str
        Returns:
            str: 파일 이름
        """
        file_name = f"{collection.value}_{date}_{suffix}.json"
        return str(Path(out_dir) / file_name)