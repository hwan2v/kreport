from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List
import json
import re

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
        default_published: bool = True,
        joiner: str = " ",
    ) -> None:
        self.default_source_id = default_source_id
        self.default_author = default_author
        self.default_published = default_published
        self.joiner = joiner

    def read_parsed_document(self, resource_file_path: str) -> Iterable[ParsedDocument]:
        docs: List[ParsedDocument] = []
        with open(resource_file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    docs.append(ParsedDocument.model_validate(json.loads(line)))
        return docs

    def _calculate_features(self, docs: List[ParsedDocument]) -> Dict[str, dict]:
        # 문서별 raw features 저장
        raw_features = {}
        feature_keys = ["body", "summary", "infobox", "paragraph"]

        for doc in docs:
            features = {}
            for b in doc.blocks:
                if b.text is None:
                    continue
                if b.type in feature_keys:
                    features[b.type] = features.get(b.type, 0) + len(b.text)
            raw_features[doc.title] = features

        # 2) 각 feature별 전체 min/max 구하기
        mins = {k: float("inf") for k in feature_keys}
        maxs = {k: float("-inf") for k in feature_keys}

        for fdict in raw_features.values():
            for k in feature_keys:
                v = fdict.get(k, 0)
                if v < mins[k]:
                    mins[k] = v
                if v > maxs[k]:
                    maxs[k] = v

        # 3) 스케일링 적용 (0~1 범위)
        scaled_features = {}
        for title, fdict in raw_features.items():
            scaled = {}
            for k in feature_keys:
                v = fdict.get(k, 0)
                if maxs[k] == mins[k]:  # 모든 값이 같으면 0으로
                    scaled[k] = 0.0
                else:
                    scaled[k] = (v - mins[k]) / (maxs[k] - mins[k])
            scaled_features[title] = scaled

        return scaled_features

    def _normalize_percentage(self, text: str) -> str:
        # 정규식: 정수부(\d+), 소수부 한 자리(\.\d), % 기호
        pattern = r"(\d+\.\d)%"

        def repl(match: re.Match) -> str:
            # 그룹1 = "22.1"
            value = float(match.group(1))
            return f"{value:.2f}%"   # 소수점 둘째 자리까지 포맷

        return re.sub(pattern, repl, text)

    def transform(self, docs: List[ParsedDocument]) -> Iterable[NormalizedChunk]:
        scaled_features = self._calculate_features(docs)
        result = []
        num = 0
        for doc in docs:
            # 1) 본문 조립
            for b in doc.blocks:
                if b.type == "body":
                    body = self._normalize_percentage(b.text)
                elif b.type == "summary":
                    summary = self._normalize_percentage(b.text)
                elif b.type == "infobox":
                    infobox = self._normalize_percentage(b.text)
                elif b.type == "paragraph":
                    paragraph = self._normalize_percentage(b.text)

            # 2) 메타 채우기(필요 시 doc.meta에서 author/date를 파싱하도록 확장 가능)
            created_date = infer_date_from_path(doc.source.uri)
            title = doc.title
            author = self.default_author
            published = self.default_published
            file_type = "html"
            source_path = doc.source.uri  # 원본 URL
            source_id = f"{self.default_source_id}_{num}"
            num += 1

            # 3) NormalizedChunk 생성 (한 건)
            chunk = NormalizedChunk(
                source_id=source_id,
                source_path=source_path,
                file_type=file_type,
                collection=doc.collection,
                title=title,
                body=body,
                paragraph=paragraph,
                summary=summary,
                infobox=infobox,
                question=None,
                answer=None,
                title_embedding=None,
                body_embedding=None,
                created_date=created_date,
                updated_date=created_date,
                author=author,
                published=published,
                features=scaled_features[title],
            )
            result.append(chunk)
        return result