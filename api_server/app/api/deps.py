# app/api/deps.py
from __future__ import annotations
from typing import Generator
from urllib.parse import urlparse

from fastapi import Depends, Request
from opensearchpy import OpenSearch

from api_server.app.domain.ports import (
    FetchPort, ParsePort, TransformPort, IndexPort, SearchPort, ListenPort
)
from api_server.app.adapters.listeners.file_listener import FileListener
from api_server.app.domain.services.search_service import SearchService
from api_server.app.domain.services.index_service import IndexService
from api_server.app.adapters.fetchers.file_fetcher import FileFetcher
from api_server.app.adapters.parsers.wiki_parser import WikiParser
from api_server.app.adapters.parsers.qna_parser import QnaParser
from api_server.app.adapters.transformers.wiki_transformer import WikiTransformer
from api_server.app.adapters.transformers.qna_transformer import QnaTransformer
from api_server.app.adapters.indexers.opensearch_indexer import OpenSearchIndexer
from api_server.app.adapters.searchers.opensearch_searcher import OpenSearchSearcher
from api_server.app.platform.config import settings


# ---- 클라이언트 ----
def get_opensearch(request: Request) -> OpenSearch:
    """
    앱 시작 시 main.py의 lifespan에서 만들어 넣어둔 OpenSearch 클라이언트를 꺼낸다.
    없으면(테스트 등) 즉석 생성.
    """
    if hasattr(request.app.state, "opensearch"):
        return request.app.state.opensearch  # type: ignore[attr-defined]

    # fallback: 즉석 생성 (테스트/단일 프로세스용)
    u = urlparse(settings.OPENSEARCH_HOST)
    return OpenSearch(
        hosts=[
            {"host": u.hostname, "port": u.port or 9200, "scheme": u.scheme or "http"}
        ],
        verify_certs=False,
    )


# ---- 어댑터(구현) ----
def get_fetcher() -> FetchPort:
    return FileFetcher()

def get_parser() -> ParsePort:
    return WikiParser()

def get_indexer(os: OpenSearch = Depends(get_opensearch)) -> IndexPort:
    # OpenSearchIndexer expects (client, prefix_index_name, alias_name)
    return OpenSearchIndexer(os, settings.OPENSEARCH_INDEX, settings.OPENSEARCH_ALIAS)

class PipelineResolver:
    """source_type에 맞는 SearchService 조립기."""
    def __init__(self, os: OpenSearch) -> None:
        self._indexer: IndexPort = OpenSearchIndexer(
            os, 
            settings.OPENSEARCH_INDEX, 
            settings.OPENSEARCH_ALIAS)
        self._searcher: SearchPort = OpenSearchSearcher(os, settings.OPENSEARCH_ALIAS)

    def for_type(self, source_type: str) -> IndexService:
        listener: ListenPort = FileListener()
        fetcher: FetchPort = FileFetcher()

        if source_type == "html":
            parser: ParsePort = WikiParser() 
            transformer: TransformPort = WikiTransformer(default_source_id="html")
        elif source_type == "tsv":
            parser: ParsePort = QnaParser()
            transformer: TransformPort = QnaTransformer(default_source_id="tsv")
        else:
            raise ValueError(f"unsupported source_type: {source_type}")

        return IndexService(
            listener=listener,
            fetcher=fetcher, 
            parser=parser, 
            transformer=transformer, 
            indexer=self._indexer
        )

def get_pipeline_resolver(os: OpenSearch = Depends(get_opensearch)) -> PipelineResolver:
    return PipelineResolver(os)

def get_search_service(os: OpenSearch = Depends(get_opensearch)) -> SearchService:
    # Wire SearchService with OpenSearchSearcher, not the raw OpenSearch client
    searcher: SearchPort = OpenSearchSearcher(os, settings.OPENSEARCH_ALIAS)
    return SearchService(searcher)