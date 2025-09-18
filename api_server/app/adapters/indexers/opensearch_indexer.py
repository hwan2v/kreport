from __future__ import annotations
import json
import os
from typing import Iterable, Any
from opensearchpy import OpenSearch, helpers
from api_server.app.domain.ports import IndexPort
from api_server.app.domain.models import NormalizedChunk, IndexResult, IndexErrorItem

class OpenSearchIndexer(IndexPort):
    """NormalizedChunk들을 OpenSearch에 bulk 적재하는 어댑터."""
    def __init__(self, client: OpenSearch, index: str) -> None:
        self.client, self.index = client, index
        self._load_index_schema()
        
    def _load_index_schema(self) -> None:
        """Load index schema from the JSON file."""
        schema_path = os.path.join(os.path.dirname(__file__), "../../../resources/schema/search_index.json")
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.index_schema = json.load(f)
            print(self.index_schema)
    
    @staticmethod
    def create_index_name(alias_name: str, index_date: str) -> str:
        return f"{alias_name}-{index_date}"
    
    @staticmethod
    def get_alias_name(index_name: str) -> str:
        return index_name.split("-")[0]
    
    def create_index(self, alias_name: str, index_date: str) -> None:
        """Create index using the loaded schema."""
        index_name = OpenSearchIndexer.create_index_name(alias_name, index_date)
        if self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
            return
        
        self.client.indices.create(index=index_name, body=self.index_schema)
        print(f"Index '{index_name}' created successfully.")
    
    def delete_alias(self, alias_name: str) -> None:
        """Delete existing alias."""
        if not self.client.indices.exists_alias(name=alias_name):
            print(f"Alias '{alias_name}' does not exist.")
            return
        
        self.client.indices.delete_alias(name=alias_name, index="_all")
        print(f"Alias '{alias_name}' deleted successfully.")
    
    def alias_index(self, alias_name: str, index_date: str) -> None:
        """Alias index using the loaded schema."""
        index_name = OpenSearchIndexer.create_index_name(alias_name, index_date)
        if self.client.indices.exists_alias(name=alias_name):
            print(f"Alias '{alias_name}' already exists.")
            self.delete_alias(alias_name)
        
        self.client.indices.put_alias(index=index_name, name=alias_name)
        print(f"Alias '{alias_name}' created successfully.")

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
