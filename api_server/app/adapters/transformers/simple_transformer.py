from __future__ import annotations

import hashlib
import re
from typing import Iterable

from api_server.app.domain.ports import TransformPort
from api_server.app.domain.models import ParsedDocument, NormalizedChunk


def _stable_doc_id(uri: str) -> str:
    """URI로부터 안정적인 문서 ID 생성(SHA1 10자리)."""
    h = hashlib.sha1(uri.encode("utf-8")).hexdigest()[:10]
    return f"doc_{h}"

_WS_RE = re.compile(r"\s+")

def _normalize_text(s: str) -> str:
    """공백 정리 등 간단 정규화."""
    return _WS_RE.sub(" ", s).strip()

def _chunk_by_chars(paragraphs: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    """
    문단 리스트를 받아 최대 글자수 기준으로 청킹.
    - overlap_chars: 다음 청크에 앞부분을 일부 겹치게 포함(검색 recall ↑)
    """
    chunks: list[str] = []
    buf: list[str] = []
    cur_len = 0

    for para in paragraphs:
        if not para:
            continue
        p = _normalize_text(para)
        if not p:
            continue

        # 새 문단을 넣으면 max를 넘는다면, 현재 버퍼를 청크로 보내고 버퍼 초기화
        if buf and (cur_len + 1 + len(p) > max_chars):
            chunks.append(" ".join(buf))
            if overlap_chars > 0:
                # 끝에서 overlap 길이만큼 가져와 다음 청크 시작에 넣기
                tail = (" ".join(buf))[-overlap_chars:]
                # 단어 중간 끊김 최소화를 위해 공백 기준으로 정리
                tail = tail.split(" ", 1)[-1] if " " in tail else tail
                buf = [tail] if tail else []
                cur_len = len(tail)
            else:
                buf, cur_len = [], 0

        # 버퍼에 문단 추가
        if cur_len == 0:
            buf = [p]
            cur_len = len(p)
        else:
            buf.append(p)
            cur_len += 1 + len(p)  # 공백 1 포함

    # 남은 버퍼 flush
    if buf:
        chunks.append(" ".join(buf))

    # 빈 문자열 제거
    return [c for c in chunks if c]


class SimpleTransformer(TransformPort):
    """
    ParsedDocument → NormalizedChunk[*] 변환기.

    전략:
      - ParsedBlock(type='paragraph') 들을 모아 글자 수 기준으로 청킹
      - 공백 정규화
      - (옵션) 청크 간 겹침(overlap)으로 검색 리콜 향상
    """

    def __init__(
        self,
        max_chars: int = 1200,
        overlap_chars: int = 120,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must be >= 0")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def transform(self, doc: ParsedDocument, collection: str) -> Iterable[NormalizedChunk]:
        uri = doc.source.uri
        doc_id = _stable_doc_id(uri)
        title = doc.title
        lang = doc.lang

        # 1) 문단만 추출(파서에서 넣어준 block.type == "paragraph")
        paragraphs: list[str] = []
        for b in doc.blocks:
            if b.type == "paragraph" and b.text:
                paragraphs.append(b.text)

        # 파서가 문단을 못 뽑았다면, meta/fallback로 페이지 전체를 하나로 처리
        if not paragraphs and doc.meta.get("page_text"):
            paragraphs = [str(doc.meta["page_text"])]

        # 2) 청킹
        bodies = _chunk_by_chars(paragraphs, self.max_chars, self.overlap_chars)

        # 3) NormalizedChunk 생성
        for i, body in enumerate(bodies):
            yield NormalizedChunk(
                collection=collection,
                doc_id=doc_id,
                seq=i,
                title=title,
                content=body,
                url=uri,
                lang=lang,
                meta={},           # 필요 시 writer/date 등 추가
                embedding=None,    # 추후 벡터 검색 붙일 때 채우기
            )
