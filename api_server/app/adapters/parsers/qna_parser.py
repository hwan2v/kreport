"""
TSV 파일을 파싱하여 ParsedDocument로 변환하는 구현체.
"""

from __future__ import annotations
from typing import List, Dict
import csv
import io

from api_server.app.domain.ports import ParsePort
from api_server.app.domain.models import ParsedDocument, ParsedBlock, RawDocument
from api_server.app.platform.exceptions import DomainError, InvalidInput

REQUIRED_COLS = {"id", "question", "answer", "published", "user_id"}

class QnaParser(ParsePort):
    
    def parse(self, raw: RawDocument) -> ParsedDocument:
        """
        TSV 텍스트를 읽어 각 행을 ParsedBlock(meta=row)으로 담는다.
        Args:
            raw: 파싱할 RawDocument
        Returns:
            ParsedDocument: 파싱된 문서
        """
        try:
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
        except ValueError as e:
            raise InvalidInput(f"invalid file format: {raw.source.uri} error={e}")
        except Exception as e:
            raise DomainError(f"failed to parse: {raw.source.uri} error={e}")