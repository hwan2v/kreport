"""
HTML에서 제목/문단/리스트/헤딩을 뽑아 NormalizedChunk로 변환하는 구현체.
    
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List
import json
import re

from api_server.app.domain.utils import infer_date_from_path
from api_server.app.domain.ports import TransformPort
from api_server.app.domain.models import ParsedDocument, NormalizedChunk

class WikiTransformer(TransformPort):
    """
    ParsedDocument(HTML) → NormalizedChunk 한 건.
    - 문단 블록(text)들을 합쳐 body를 구성
    - 제목/언어/작성자 등은 정책에 따라 채움
    """

    def __init__(
        self,
        default_source_id: str = "html",
        default_author: str | None = None,
        default_published: bool = True
    ) -> None:
        self.default_source_id = default_source_id
        self.default_author = default_author
        self.default_published = default_published

    def read_parsed_document(self, resource_file_path: str) -> List[ParsedDocument]:
        """
        json 파일을 읽어 ParsedDocument로 변환하는 메서드.
        Args:
            resource_file_path: str (json 파일 경로)
        Returns:
            List[ParsedDocument]
        """
        docs: List[ParsedDocument] = []
        with open(resource_file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    docs.append(ParsedDocument.model_validate(json.loads(line)))
        return docs

    def _calculate_features(self, docs: List[ParsedDocument]) -> Dict[str, dict]:
        """
        문서별 raw features 계산하여 반환하는 메서드(검색 스코어 계산에 사용)
        - feature_keys: body, summary, infobox, paragraph
        - 각 feature별 전체 min/max 구하기
        - 스케일링 적용 (0~1 범위)

        Args:
            docs: List[ParsedDocument]
        Returns:
            Dict[str, dict]: 문서별 raw features
        """
        raw_features = {}
        feature_keys = ["body", "summary", "infobox", "paragraph"]

        # 문서별 features의 길이 구하기
        for doc in docs:
            features = {}
            for b in doc.blocks:
                if b.text is None:
                    continue
                if b.type in feature_keys:
                    features[b.type] = features.get(b.type, 0) + len(b.text)
            raw_features[doc.title] = features

        # 각 feature별 전체 min/max 구하기
        mins = {k: float("inf") for k in feature_keys}
        maxs = {k: float("-inf") for k in feature_keys}

        for fdict in raw_features.values():
            for k in feature_keys:
                v = fdict.get(k, 0)
                if v < mins[k]:
                    mins[k] = v
                if v > maxs[k]:
                    maxs[k] = v

        # 스케일링 적용 (0~1 범위)
        scaled_features = {}
        for title, fdict in raw_features.items():
            scaled = {}
            for k in feature_keys:
                v = fdict.get(k, 0)
                if maxs[k] == mins[k]:
                    scaled[k] = 0.0
                else:
                    scaled[k] = (v - mins[k]) / (maxs[k] - mins[k])
            scaled_features[title] = scaled

        return scaled_features

    def _normalize_percentage(self, text: str) -> str:
        """
        퍼센트 포맷을 소수점 둘째 자리까지 포맷하는 메서드.
        Args:
            text: str
        Returns:
            str
        """
        # 정규식: 정수부(\d+), 소수부 한 자리(\.\d), % 기호
        pattern = r"(\d+\.\d)%"

        def repl(match: re.Match) -> str:
            # 81번 질문
            # 소수점을 그룹1로 추출하여 소수점 둘째 자리까지 포맷 변환
            value = float(match.group(1))
            return f"{value:.2f}%"

        return re.sub(pattern, repl, text)

    def transform(self, docs: List[ParsedDocument]) -> List[NormalizedChunk]:
        """
        ParsedDocument를 NormalizedChunk로 변환하는 메서드.
        parsed document의 블록을 참조하여 NormalizedChunk를 생성한다.
        Args:
            docs: List[ParsedDocument]
        Returns:
            List[NormalizedChunk]
        """
        scaled_features = self._calculate_features(docs)
        result = []
        num = 0
        for doc in docs:
            # 본문 추출
            for b in doc.blocks:
                if b.type == "body":
                    body = self._normalize_percentage(b.text)
                elif b.type == "summary":
                    summary = self._normalize_percentage(b.text)
                elif b.type == "infobox":
                    infobox = self._normalize_percentage(b.text)
                elif b.type == "paragraph":
                    paragraph = self._normalize_percentage(b.text)

            created_date = infer_date_from_path(doc.source.uri)
            title = doc.title
            author = self.default_author
            published = self.default_published
            file_type = "html"
            source_path = doc.source.uri  # 원본 URL
            source_id = f"{self.default_source_id}_{num}"
            num += 1

            # NormalizedChunk 생성성
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