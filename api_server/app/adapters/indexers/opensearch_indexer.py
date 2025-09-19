from __future__ import annotations
import json
import os
from typing import Iterable, Any, List, Dict, Tuple
import re
from opensearchpy import OpenSearch, helpers
from api_server.app.domain.ports import IndexPort
from api_server.app.domain.models import NormalizedChunk, IndexResult, IndexErrorItem

class OpenSearchIndexer(IndexPort):
    """NormalizedChunk들을 OpenSearch에 bulk 적재하는 어댑터."""
    def __init__(self, client: OpenSearch, prefix_index_name: str, alias_name: str) -> None:
        self.client = client
        self.prefix_index_name = prefix_index_name
        self.alias_name = alias_name
        self._load_index_schema()
        
    def _load_index_schema(self) -> None:
        """Load index schema from the JSON file."""
        schema_path = os.path.join(os.path.dirname(__file__), "../../../resources/schema/search_index.json")
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.index_schema = json.load(f)
            print(self.index_schema)
    
    def _create_index_name(self, source: str, index_date: str) -> str:
        return f"{self.prefix_index_name}-{source}-{index_date}"
        
    def create_index(self, source: str, index_date: str) -> None:
        """Create index using the loaded schema."""
        index_name = self._create_index_name(source, index_date)
        if self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
            return index_name
        
        self.client.indices.create(index=index_name, body=self.index_schema)
        print(f"Index '{index_name}' created successfully.")
        return index_name

    def index(self, index_name: str, resource_file_path: str) -> None:
        chunks: List[NormalizedChunk] = []
        with open(resource_file_path, "r", encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line.strip())
                chunks.append(NormalizedChunk.model_validate(doc))

        return self._index(index_name, chunks)

    def _index(self, index_name: str, chunks: Iterable[NormalizedChunk]) -> IndexResult:
        # Pydantic v2 → JSON 호환 dict
        def actions():
            for c in chunks:
                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": c.source_id,
                    "_source": c.model_dump(mode="json"),
                }

        ok, errors = helpers.bulk(self.client, actions(), raise_on_error=False)
        err_items: list[IndexErrorItem] = []
        for e in errors or []:
            # 에러 구조가 다양해서 안전하게 문자열화
            err_items.append(IndexErrorItem(
                doc_id=str(e.get("index", {}).get("_id", "")),
                seq=0,  # 필요시 source에 seq를 넣고 꺼내서 기록
                reason=str(e)))
        return IndexResult(indexed=ok, errors=err_items)

    # ================== alias ==================
    def delete_alias(self, alias_name: str) -> None:
        """Delete existing alias."""
        if not self.client.indices.exists_alias(name=alias_name):
            print(f"Alias '{alias_name}' does not exist.")
            return
        
        self.client.indices.delete_alias(name=alias_name, index="_all")
        print(f"Alias '{alias_name}' deleted successfully.")
    
    def add_alias(self, alias_name: str, index_names: List[str]) -> None:
        """Alias index using the loaded schema."""
        if self.client.indices.exists_alias(name=alias_name):
            print(f"Alias '{alias_name}' already exists.")
        
        for index_name in index_names:
            if self.client.indices.exists(index=index_name):
                self.client.indices.put_alias(index=index_name, name=alias_name)
                print(f"Alias '{alias_name}' created successfully.")
            else:
                print(f"Index '{index_name}' does not exist.")
        return alias_name

    def rotate_alias_to_latest(self, alias_name: str, base_prefix: str, delete_old: bool = True) -> List[str]:
        """
        Rotate alias to point to the latest versioned indices and (optionally) delete older indices.

        Assumes index naming scheme: {base_prefix}-{group}-{version}
        Examples:
          my-index-html-1, my-index-html-2, my-index-tsv-3

        - Picks the highest numeric version per group (e.g., html, tsv)
        - Updates alias atomically to point only to those latest indices
        - Optionally deletes older indices

        Returns:
            List[str]: The list of latest index names that the alias points to
        """
        pattern = f"{base_prefix}-*"
        try:
            all_indices_map: Dict[str, Any] = self.client.indices.get(index=pattern)
        except Exception as e:
            print(f"Failed to list indices for pattern '{pattern}': {e}")
            return []

        all_index_names: List[str] = sorted(all_indices_map.keys())
        if not all_index_names:
            print(f"No indices found for pattern '{pattern}'.")
            return []

        # Group by middle part (group), pick max version per group
        latest_by_group: Dict[str, Tuple[int, str]] = {}
        base_escaped = re.escape(base_prefix)
        regex = re.compile(rf"^{base_escaped}-(?P<group>.+)-(?P<ver>\d+)$")

        for name in all_index_names:
            m = regex.match(name)
            if not m:
                # Skip indices that don't match the expected pattern
                continue
            group = m.group("group")
            try:
                ver = int(m.group("ver"))
            except ValueError:
                continue
            current = latest_by_group.get(group)
            if current is None or ver > current[0]:
                latest_by_group[group] = (ver, name)

        latest_indices: List[str] = [name for (_, name) in sorted(latest_by_group.values())]
        if not latest_indices:
            print(f"No indices matched the expected versioned pattern under '{base_prefix}'.")
            return []

        # Build alias actions for atomic switch
        actions: List[Dict[str, Any]] = []
        if self.client.indices.exists_alias(name=alias_name):
            try:
                current_alias_map = self.client.indices.get_alias(name=alias_name)
                for idx in current_alias_map.keys():
                    actions.append({"remove": {"index": idx, "alias": alias_name}})
            except Exception as e:
                print(f"Failed to fetch existing alias '{alias_name}': {e}")

        for idx in latest_indices:
            actions.append({"add": {"index": idx, "alias": alias_name}})

        if actions:
            self.client.indices.update_aliases(body={"actions": actions})
            print(f"Alias '{alias_name}' now points to: {', '.join(latest_indices)}")

        if delete_old:
            latest_set = set(latest_indices)
            to_delete = [n for n in all_index_names if n not in latest_set]
            for idx in to_delete:
                try:
                    self.client.indices.delete(index=idx, ignore=[404])
                    print(f"Deleted old index: {idx}")
                except Exception as e:
                    print(f"Failed to delete index '{idx}': {e}")

        return latest_indices