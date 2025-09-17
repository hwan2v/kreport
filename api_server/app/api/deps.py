# app/api/deps.py
from __future__ import annotations
from typing import Generator
from urllib.parse import urlparse

from fastapi import Depends, Request
from opensearchpy import OpenSearch

from app.domain.ports import FetchPort, ParsePort, TransformPort, IndexPort
from app.domain.services.extract_service import ExtractService

from app.adapters.fetchers.http_fetcher import HttpFetcher
from app.adapters.parsers.bs4_parser import Bs4ArticleParser
from app.adapters.transformers.simple_transformer import SimpleTransformer
from app.adapters.indexers.opensearch_indexer import OpenSearchIndexer

from app.platform.config import settings


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
    return HttpFetcher(timeout=10.0)

def get_parser() -> ParsePort:
    return Bs4ArticleParser()

def get_transformer() -> TransformPort:
    # 필요시 settings에서 파라미터 받기
    return SimpleTransformer(max_chars=1200, overlap_chars=120)

def get_indexer(os: OpenSearch = Depends(get_opensearch)) -> IndexPort:
    return OpenSearchIndexer(os, settings.OPENSEARCH_INDEX)


# ---- 유스케이스 서비스(오케스트레이션) ----
def get_extract_service(
    fetcher: FetchPort = Depends(get_fetcher),
    parser: ParsePort = Depends(get_parser),
    transformer: TransformPort = Depends(get_transformer),
    indexer: IndexPort = Depends(get_indexer),
) -> ExtractService:
    return ExtractService(fetcher, parser, transformer, indexer)
