"""
NormalizedChunk들을 OpenSearch에 색인하는 IndexPort 구현체
"""

from __future__ import annotations
import json
import os
import re
from typing import Any, List, Dict, Tuple
from pathlib import Path
from opensearchpy import OpenSearch, helpers
from api_server.app.domain.ports import IndexPort
from api_server.app.domain.models import (
    NormalizedChunk, IndexResult, IndexErrorItem, AliasResult
)

class OpenSearchIndexer(IndexPort):
    
    def __init__(self, client: OpenSearch, prefix_name: str, alias_name: str) -> None:
        self.client = client
        self.prefix_name = prefix_name
        self.alias_name = alias_name
        self._load_index_schema()
        
    def _load_index_schema(self) -> None:
        """
            인덱스 스키마를 JSON 파일에서 로드한다.
        """
        root_dir = Path(os.path.dirname(__file__)).resolve().parents[2]
        schema_path = root_dir / "resources/schema/search_index.json"
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.index_schema = json.load(f)
    
    def _create_index_name(self, source: str, index_date: str) -> str:
        return f"{self.prefix_name}-{source}-{index_date}"
        
    def create_index(self, source: str, index_date: str) -> str:
        """
            로드된 스키마를 사용해 인덱스를 생성한다.
            인덱스 이름 형식: {prefix_name}-{source}-{index_date}
            ex. myidx-html-1, myidx-tsv-2, myidx-tsv-3

            Args:
                source: 소스 이름(html, tsv)
                index_date: 인덱스 날짜(ex. 1,2,3)
            Returns:
                생성된 인덱스 이름
        """
        index_name = self._create_index_name(source, index_date)
        if self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
            return index_name
        
        self.client.indices.create(index=index_name, body=self.index_schema)
        print(f"Index '{index_name}' created successfully.")
        return index_name

    def index(self, index_name: str, resource_file_path: str) -> IndexResult:
        """
            인덱스에 NormalizedChunk들을 색인한다.
            
            - 파일 경로에서 NormalizedChunk들을 읽어와 색인한다.
            - 색인 결과를 반환한다.

            Args:
                index_name: 인덱스 이름
                resource_file_path: NormalizedChunk들이 저장된 파일 경로
            Returns:
                색인 결과(색인 성공/실패 건수, 실패 상세, 인덱스 이름, 별칭)
        """
        chunks: List[NormalizedChunk] = []
        with open(resource_file_path, "r", encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line.strip())
                if self._is_published(doc):
                    chunks.append(NormalizedChunk.model_validate(doc))
        return self._index(index_name, chunks)

    def _is_published(self, doc: dict) -> bool:
        """
            문서가 공개되었는지 확인한다.
            Args:
                doc: 문서
            Returns:
                bool: 문서가 공개되었는지 여부
        """
        return doc.get("published", True)

    def _index(self, index_name: str, chunks: List[NormalizedChunk]) -> IndexResult:
        """
            인덱스에 NormalizedChunk들을 색인한다.
            
            Args:
                index_name: 인덱스 이름
                chunks: NormalizedChunk들
            Returns:
                색인 결과(색인 성공/실패 건수, 실패 상세, 인덱스 이름, 별칭)
        """
        def actions():
            for c in chunks:
                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": c.source_id,
                    "_source": c.model_dump(mode="json"),
                }

        # bulk 적재
        ok, errors = helpers.bulk(self.client, actions(), raise_on_error=False)
        err_items: list[IndexErrorItem] = []
        for e in errors or []:
            err_items.append(IndexErrorItem(
                doc_id=str(e.get("index", {}).get("_id", "")),
                seq=0,
                reason=str(e)))
        return IndexResult(indexed=ok, errors=err_items)

    # ================== alias ==================
    def rotate_alias_to_latest(
        self, 
        alias_name: str, 
        base_prefix: str, 
        delete_old: bool = True) -> AliasResult:
        """
        alias를 최신 버전 인덱스로 회전(갱신)하고, 필요 시 오래된 인덱스를 삭제한다.

        인덱스 네이밍 규칙 가정: {base_prefix}-{group}-{date}
        ex) my-index-html-1, my-index-html-2, my-index-tsv-3

        동작 방식:
        - 동일 그룹(group)별로 가장 최신 날짜(date) 인덱스를 선택
        - alias를 원자적으로 최신 인덱스로만 갱신
        - 옵션(delete_old=True)일 경우 오래된 인덱스는 삭제

        Args:
            alias_name: alias 이름
            base_prefix: 인덱스 네이밍 규칙 접두사
            delete_old: 오래된 인덱스 삭제 여부
        Returns:
            AliasResult: alias가 가리키는 최신 인덱스 목록
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

        # 그룹(group)별로 가장 최신 날짜(date) 인덱스를 선택
        latest_by_group: Dict[str, Tuple[int, str]] = {}
        base_escaped = re.escape(base_prefix)
        regex = re.compile(rf"^{base_escaped}-(?P<group>.+)-(?P<ver>\d+)$")

        for name in all_index_names:
            m = regex.match(name)
            if not m:
                # 패턴에 맞지 않는 인덱스는 스킵
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

        # alias를 최신 인덱스로만 갱신하기 위해 기존 index 제거
        actions: List[Dict[str, Any]] = []
        if self.client.indices.exists_alias(name=alias_name):
            try:
                current_alias_map = self.client.indices.get_alias(name=alias_name)
                for idx in current_alias_map.keys():
                    actions.append({"remove": {"index": idx, "alias": alias_name}})
            except Exception as e:
                print(f"Failed to fetch existing alias '{alias_name}': {e}")

        # alias를 최신 인덱스로만 갱신
        for idx in latest_indices:
            actions.append({"add": {"index": idx, "alias": alias_name}})

        # alias 업데이트
        if actions:
            self.client.indices.update_aliases(body={"actions": actions})
            print(f"Alias '{alias_name}' now points to: {', '.join(latest_indices)}")

        # 옵션(delete_old=True)일 경우 오래된 인덱스는 삭제
        if delete_old:
            latest_set = set(latest_indices)
            to_delete = [n for n in all_index_names if n not in latest_set]
            for idx in to_delete:
                try:
                    self.client.indices.delete(index=idx, ignore=[404])
                    print(f"Deleted old index: {idx}")
                except Exception as e:
                    print(f"Failed to delete index '{idx}': {e}")

        return AliasResult(
            index_name=latest_indices,
            alias_name=alias_name
        )