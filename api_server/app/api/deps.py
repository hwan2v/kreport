# app/api/deps.py
from __future__ import annotations
from typing import Generator
from urllib.parse import urlparse

from fastapi import Depends, Request
from opensearchpy import OpenSearch

from api_server.app.domain.ports import FetchPort, ParsePort, TransformPort, IndexPort
from api_server.app.domain.services.search_service import SearchService

from api_server.app.adapters.fetchers.file_fetcher import FileFetcher
from api_server.app.adapters.parsers.bs4_parser import Bs4Parser
from api_server.app.adapters.parsers.tsv_parser import TsvParser
from api_server.app.adapters.transformers.html_transformer import HtmlTransformer
from api_server.app.adapters.transformers.tsv_transformer import TsvTransformer
from api_server.app.adapters.transformers.simple_transformer import SimpleTransformer
from api_server.app.adapters.indexers.opensearch_indexer import OpenSearchIndexer

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
        hosts=[{"host": u.hostname, "port": u.port or 9200, "scheme": u.scheme or "http"}],
        verify_certs=False,
    )


# ---- 어댑터(구현) ----
def get_fetcher() -> FetchPort:
    return FileFetcher()

def get_parser() -> ParsePort:
    return Bs4Parser()

def get_transformer() -> TransformPort:
    # 필요시 settings에서 파라미터 받기
    return SimpleTransformer(max_chars=1200, overlap_chars=120)

def get_indexer(os: OpenSearch = Depends(get_opensearch)) -> IndexPort:
    return OpenSearchIndexer(os, settings.OPENSEARCH_INDEX)


class PipelineResolver:
    """source_type에 맞는 SearchService 조립기."""
    def __init__(self, os: OpenSearch) -> None:
        self._indexer: IndexPort = OpenSearchIndexer(os, settings.OPENSEARCH_INDEX)

    def for_type(self, source_type: str) -> SearchService:
        # 공통 fetcher (필요하면 tsv에 file_fetcher로 바꾸도록 확장)
        fetcher: FetchPort = FileFetcher()

        if source_type == "html":
            parser: ParsePort = Bs4Parser()
            transformer: TransformPort = HtmlTransformer(default_source_id="html")
        elif source_type == "tsv":
            parser: ParsePort = TsvParser()
            transformer: TransformPort = TsvTransformer(default_source_id="tsv")
        else:
            raise ValueError(f"unsupported source_type: {source_type}")

        return SearchService(fetcher=fetcher, parser=parser,
                              transformer=transformer, indexer=self._indexer)

def get_pipeline_resolver(os: OpenSearch = Depends(get_opensearch)) -> PipelineResolver:
    return PipelineResolver(os)

# ---- 유스케이스 서비스(오케스트레이션) ----
def get_search_service(
    fetcher: FetchPort = Depends(get_fetcher),
    parser: ParsePort = Depends(get_parser),
    transformer: TransformPort = Depends(get_transformer),
    indexer: IndexPort = Depends(get_indexer),
) -> SearchService:
    return SearchService(fetcher, parser, transformer, indexer)
