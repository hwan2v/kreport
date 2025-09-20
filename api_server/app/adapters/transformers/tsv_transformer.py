from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Iterable, List
import json

from api_server.app.domain.utils import infer_date_from_path
from api_server.app.domain.ports import TransformPort
from api_server.app.domain.models import ParsedDocument, NormalizedChunk

class TsvTransformer(TransformPort):
    """
    TSV ParsedDocument → NormalizedChunk[*]
    (※ 기존 TransformPort가 NormalizedChunk를 반환했다면,
       이 구현은 NormalizedChunk 반환하도록 프로젝트에 맞춰 인터페이스를 살짝 조정하거나
       Indexer에서 dict/NormalizedChunk 모두 처리하게 만들어도 됩니다.)
    """

    def __init__(self, default_source_id: str = "tsv"):
        self.default_source_id = default_source_id

    def read_parsed_document(self, resource_file_path: str) -> Iterable[ParsedDocument]:
        with open(resource_file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        docs: List[ParsedDocument] = []
        if isinstance(payload, list):
            for item in payload:
                docs.append(ParsedDocument.model_validate(item))
        elif isinstance(payload, dict):
            data = payload.get("data") if "data" in payload else None
            if isinstance(data, list):
                for item in data:
                    docs.append(ParsedDocument.model_validate(item))
            else:
                docs.append(ParsedDocument.model_validate(payload))
        else:
            raise ValueError("Unsupported JSON format for ParsedDocument deserialization")
        return docs

    def transform(self, docs: List[ParsedDocument]) -> Iterable[NormalizedChunk]:
        result = []
        for doc in docs:
            created_date = infer_date_from_path(doc.source.uri)
            uri = doc.source.uri
            for i, b in enumerate(doc.blocks):
                if b.type != "row":
                    continue
                row = b.meta  # Dict[str, str]
                # 매핑 규칙
                id = row.get('id')
                source_id   = f"{self.default_source_id}_{id}"
                source_path = uri
                file_type   = doc.source.file_type
                question       = row.get("question") or None
                answer        = row.get("answer") or ""
                author      = row.get("user_id") or None
                published     = (row.get("published") or "").upper().startswith("Y")

                chunk = NormalizedChunk(
                    source_id=source_id,
                    source_path=source_path,
                    file_type=file_type,
                    collection=doc.collection,
                    title=None,
                    body=None,
                    paragraph=None,
                    summary=None,
                    infobox=None,
                    question=question,
                    answer=answer,
                    title_embedding=None,   # 필요 시 임베딩 생성기로 채우기
                    body_embedding=None,    # 필요 시 임베딩 생성기로 채우기
                    created_date=created_date,       # TSV에 날짜가 없으므로 현재 시각 사용(또는 정책에 맞게 변경)
                    updated_date=created_date,
                    author=author,
                    published=published,
                    features=None,
                )
                result.append(chunk)
        return result

