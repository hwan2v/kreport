"""
사용자 검색 쿼리를 받아 검색하는 SearchPort 구현체.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict
from opensearchpy import OpenSearch
from api_server.app.domain.ports import SearchPort

class OpenSearchSearcher(SearchPort):
    
    def __init__(self, client: OpenSearch, alias_name: str) -> None:
        self.client = client
        self.alias_name = alias_name

    def search(self, query: str, size: int = 3, explain: bool = False) -> Dict[str, Any]:
        """
        Opensearch에 검색을 수행하여 결과를 반환한다.

        Args:
            query (str): 검색어
            size (int): 가져올 문서 개수 (기본 3)
            explain (bool): 검색 결과 설명 포함 여부 (기본 False)
        Returns:
            Dict[str, Any]: 검색 결과(hits, total, took, timed_out)
        """
        body = self._build_query(query, size=size, explain=explain)
        return self.client.search(index=self.alias_name, body=body)

    def _build_query(
        self, 
        query: str, 
        size: int = 3, 
        explain: bool = False, 
        min_score: float = 5) -> Dict[str, Any]:
        """
        검색 쿼리 바디를 구성한다.

        Args:
            query (str): 검색어
            size (int): 가져올 문서 개수 (기본 3)
            explain (bool): 검색 결과 설명 포함 여부 (기본 False)
            min_score (float): 최소 점수 (기본 5)
        Returns:
            Dict[str, Any]: 검색 쿼리 바디
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
                                # {
                                #     "multi_match": {
                                #         "query": query,
                                #         "fields": ["question.ko_nori_mixed", "question.ngram"],
                                #         "type": "best_fields",
                                #         "operator": "or"
                                #     }
                                # },
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