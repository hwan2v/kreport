from __future__ import annotations
from typing import Iterable, Any
from opensearchpy import OpenSearch, helpers
from app.domain.ports import IndexPort
from app.domain.models import NormalizedChunk, IndexResult, IndexErrorItem

class OpenSearchIndexer(IndexPort):
    """NormalizedChunk들을 OpenSearch에 bulk 적재하는 어댑터."""
    def __init__(self, client: OpenSearch, index: str) -> None:
        self.client, self.index = client, index

    def index(self, chunks: Iterable[NormalizedChunk]) -> IndexResult:
        # Pydantic v2 → JSON 호환 dict
        def actions():
            for c in chunks:
                yield {
                    "_op_type": "index",
                    "_index": self.index,
                    "_source": c.model_dump(mode="json"),
                }

        ok, errors = helpers.bulk(self.client, actions(), raise_on_error=False)
        err_items: list[IndexErrorItem] = []
        for e in errors or []:
            # 에러 구조가 다양해서 안전하게 문자열화
            err_items.append(IndexErrorItem(doc_id=str(e.get("index", {}).get("_id", "")),
                                            seq=0,  # 필요시 source에 seq를 넣고 꺼내서 기록
                                            reason=str(e)))
        return IndexResult(indexed=ok, errors=err_items)
