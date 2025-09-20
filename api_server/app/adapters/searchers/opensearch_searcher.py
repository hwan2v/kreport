from __future__ import annotations
import json
import os
from typing import Iterable, Any, Dict
from opensearchpy import OpenSearch, helpers
from api_server.app.domain.ports import SearchPort
from api_server.app.domain.models import NormalizedChunk, IndexResult, IndexErrorItem

class OpenSearchSearcher(SearchPort):
    """NormalizedChunk들을 OpenSearch에 bulk 적재하는 어댑터."""
    def __init__(self, client: OpenSearch, alias_name: str) -> None:
        self.client = client
        self.alias_name = alias_name

    def search(self, query: str, size: int = 3) -> [NormalizedChunk]:
        body = self._build_query(query, size)
        return self.client.search(index=self.alias_name, body=body)

    def _build_query(self, query: str, size: int = 3) -> Dict[str, Any]:
        """
        title, body 양쪽을 대상으로 keyword 검색 후 상위 N개 반환.
        Args:
            query (str): 검색어
            size (int): 가져올 문서 개수 (기본 3)
        Returns:
            list of _source dict
        """
        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title", "body", "question", "answer"],
                    "type": "best_fields",
                    "operator": "or"
                }
            }
        }
        return body