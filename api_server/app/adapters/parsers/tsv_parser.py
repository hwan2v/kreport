from __future__ import annotations
from typing import Sequence, List, Dict
import csv
import io

from api_server.app.domain.ports import ParsePort
from api_server.app.domain.models import ParsedDocument, ParsedBlock, RawDocument

REQUIRED_COLS = {"id", "question", "answer", "published", "user_id"}

class TsvParser(ParsePort):
    """
    TSV 텍스트를 읽어 각 행을 ParsedBlock(meta=row)으로 담는다.
    todo: TSV를 행(dict) 리스트로 안전하게 파싱 + 스키마 검증/클린업
    """
    def parse(self, raw: RawDocument) -> ParsedDocument:
        text = raw.body_text or ""
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        # 헤더 검증
        cols = set(reader.fieldnames or [])
        missing = REQUIRED_COLS - cols
        if missing:
            raise ValueError(f"TSV missing columns: {sorted(missing)}")

        blocks: List[ParsedBlock] = []
        for row in reader:
            # 공백 정리
            clean: Dict[str, str] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            blocks.append(ParsedBlock(type="row", text=None, meta=clean))

        return ParsedDocument(
            source=raw.source,
            title=None,
            blocks=blocks,
            lang=None,
            meta={"rows": len(blocks), "columns": list(cols)},
            collection=raw.collection
        )