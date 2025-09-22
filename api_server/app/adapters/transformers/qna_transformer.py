"""
tsv에서 파싱된 결과를 색인 단위인 NormalizedChunk로 변환하는 TransformPort 구현체.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import List
import json

from api_server.app.domain.utils import infer_date_from_path
from api_server.app.domain.ports import TransformPort
from api_server.app.domain.models import ParsedDocument, NormalizedChunk
from api_server.app.platform.exceptions import DomainError, ResourceNotFound

class QnaTransformer(TransformPort):

    def __init__(self, default_source_id: str = "tsv"):
        self.default_source_id = default_source_id

    def read_parsed_document(self, resource_file_path: str) -> List[ParsedDocument]:
        """
        json 파일을 읽어 ParsedDocument로 변환하는 메서드.
        Args:
            resource_file_path: str (json 파일 경로)
        Returns:
            List[ParsedDocument]
        """
        try:
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
        except FileNotFoundError as e:
            raise ResourceNotFound(f"resource not found: {resource_file_path} error={e}")
        except Exception as e:
            raise DomainError(f"failed to read: qna docs. error={e}")

    def transform(self, docs: List[ParsedDocument]) -> List[NormalizedChunk]:
        """
        ParsedDocument를 NormalizedChunk로 변환하는 메서드.
        parsed document의 row 블록을 참조하여 NormalizedChunk를 생성한다.
        - 매핑 규칙: 
            id -> source_id
            question -> question
            answer -> answer 
            user_id -> author
            published -> published
        Args:
            docs: List[ParsedDocument]
        Returns:
            List[NormalizedChunk]
        """
        try:
            result = []
            for doc in docs:
                created_date = infer_date_from_path(doc.source.uri)
                uri = doc.source.uri
                for i, b in enumerate(doc.blocks):
                    if b.type != "row":
                        continue
                    row = b.meta  # Dict[str, str]
                    
                    id = row.get('id')
                    source_id   = f"{self.default_source_id}_{id}"
                    source_path = uri
                    file_type   = doc.source.file_type
                    question    = row.get("question") or None
                    answer      = row.get("answer") or ""
                    author      = row.get("user_id") or None
                    published   = (row.get("published") or "").upper().startswith("Y")

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
                        title_embedding=None,
                        body_embedding=None,
                        created_date=created_date,
                        updated_date=created_date,
                        author=author,
                        published=published,
                        features=None,
                    )
                    result.append(chunk)
            return result
        except FileNotFoundError as e:
            raise ResourceNotFound(f"resource not found: {resource_file_path} error={e}")
        except Exception as e:
            raise DomainError(f"failed to transform: qna docs. error={e}")

