from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from api_server.app.domain.utils import infer_date_from_path
from api_server.app.domain.ports import TransformPort
from api_server.app.domain.models import ParsedDocument, NormalizedChunk

class HtmlTransformer(TransformPort):
    """
    ParsedDocument(HTML) → NormalizedChunk 한 건.
    - 문단 블록(text)들을 합쳐 body를 구성
    - 제목/언어/작성자 등은 정책에 따라 채움
    """

    def __init__(
        self,
        default_source_id: str = "html",
        default_author: str | None = None,
        default_is_open: bool = True,
        joiner: str = " ",
    ) -> None:
        self.default_source_id = default_source_id
        self.default_author = default_author
        self.default_is_open = default_is_open
        self.joiner = joiner

    def transform(self, resource_file_path: str) -> Iterable[NormalizedChunk]:
        print(resource_file_path)
        with open(resource_file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        docs: List[ParsedDocument] = []
        if isinstance(payload, list):
            for item in payload:
                docs.append(ParsedDocument.model_validate(item))
        elif isinstance(payload, dict):
            # 지원: {"data": [...]} 형태도 허용
            data = payload.get("data") if "data" in payload else None
            if isinstance(data, list):
                for item in data:
                    docs.append(ParsedDocument.model_validate(item))
            else:
                docs.append(ParsedDocument.model_validate(payload))
        else:
            raise ValueError("Unsupported JSON format for ParsedDocument deserialization")

        return self.to_chunks(docs)

    def to_chunks(self, docs: List[ParsedDocument]) -> Iterable[NormalizedChunk]:
        result = []
        num = 0
        for doc in docs:
            # 1) 본문 조립
            paragraphs: list[str] = [b.text for b in doc.blocks if b.text]
            body = self.joiner.join(paragraphs).strip()

            # 2) 메타 채우기(필요 시 doc.meta에서 author/date를 파싱하도록 확장 가능)
            created_date = infer_date_from_path(doc.source.uri)
            title = doc.title
            author = self.default_author
            is_open = self.default_is_open
            file_type = "html"
            source_path = doc.source.uri  # 원본 URL
            source_id = f"{self.default_source_id}_{num}"
            num += 1

            # 3) NormalizedChunk 생성 (한 건)
            chunk = NormalizedChunk(
                source_id=source_id,
                source_path=source_path,
                file_type=file_type,
                title=title,
                body=body,
                title_embedding=None,
                body_embedding=None,
                created_date=created_date,
                updated_date=created_date,
                author=author,
                is_open=is_open,
            )
            result.append(chunk)
        return result