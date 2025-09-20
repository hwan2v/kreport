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

    def search(self, query: str, size: int = 3, explain: bool = False) -> [NormalizedChunk]:
        body = self._build_query(query, size=size, explain=explain)
        return self.client.search(index=self.alias_name, body=body)

    def _build_query(self, query: str, size: int = 3, explain: bool = False, min_score: float = 5) -> Dict[str, Any]:
        """
        title, body 양쪽을 대상으로 keyword 검색 후 상위 N개 반환.
        Args:
            query (str): 검색어
            size (int): 가져올 문서 개수 (기본 3)
        Returns:
            list of _source dict
        """
        body = {
            "from": 0,
            "size": size,
            "explain": explain,
            "min_score": min_score,
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "filter": {
                                "bool": {
                                    "must": [
                                        {
                                            "term": {
                                                "published": True
                                            }
                                        }
                                    ]
                                }
                            },
                            "should": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["title", "title.keyword"],
                                        "type": "best_fields",
                                        "operator": "or",
                                        "boost": 4
                                    }
                                },
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["question", "answer"],
                                        "type": "best_fields",
                                        "operator": "or",
                                        "boost": 2.5
                                    }
                                },
                                {
                                    "match": {
                                        "infobox": {
                                            "query": query,
                                            "boost": 2
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "paragraph": {
                                            "query": query,
                                            "boost": 2
                                        }
                                    }
                                },
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["summary", "infobox"],
                                        "type": "best_fields",
                                        "operator": "or",
                                        "boost": 2
                                    }
                                }
                            ]
                        }
                    },
                    "functions": [
                        {
                            "field_value_factor": {
                                "field": "features.body",
                                "factor": 1.5,
                                "missing": 1
                            }
                        },
                        {
                            "field_value_factor": {
                                "field": "features.summary",
                                "factor": 3,
                                "missing": 1
                            }
                        },
                        {
                            "field_value_factor": {
                                "field": "features.infobox",
                                "factor": 8,
                                "missing": 3
                            }
                        }
                    ],
                    "score_mode": "avg",
                    "boost_mode": "sum"
                }
            }
        }
        return body