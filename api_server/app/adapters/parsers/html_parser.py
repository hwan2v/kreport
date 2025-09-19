from __future__ import annotations
from typing import Sequence
from bs4 import BeautifulSoup

from api_server.app.domain.ports import ParsePort
from api_server.app.domain.models import ParsedDocument, ParsedBlock, RawDocument

class HtmlParser(ParsePort):
    """HTML에서 제목/문단/리스트/헤딩을 뽑아 ParsedDocument로 변환."""

    # 위키, 블로그 등에서 본문 외 요소 제거용 셀렉터
    _STRIP_SELECTORS = [
        "script", "style", "noscript", "header", "footer", "nav",
        "aside", ".toc", ".infobox", ".mw-references-wrap", "sup.reference",
        ".catlinks", ".navbox", ".metadata", ".hatnote", ".mw-editsection",
    ]

    def parse(self, raw: RawDocument) -> ParsedDocument:
        html = raw.body_text or ""
        soup = BeautifulSoup(html, "lxml")

        # 1) title/lang
        title_tag = soup.select_one("h1") or soup.select_one("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        lang = (soup.html.get("lang") if soup.html else None) or None

        # 2) 불필요한 요소 제거
        for sel in self._STRIP_SELECTORS:
            for el in soup.select(sel):
                el.decompose()

        # 3) 본문 컨테이너 힌트(위키: #mw-content-text)
        content_root: Tag = soup.select_one("#mw-content-text") or soup.body or soup

        blocks: list[ParsedBlock] = []

        # 4) 헤딩 → paragraph로 포함 (검색용)
        for h in content_root.select("h1, h2, h3, h4, h5, h6"):
            text = h.get_text(" ", strip=True)
            if text:
                blocks.append(ParsedBlock(type="paragraph", text=text, meta={"kind": "heading"}))

        # 5) 문단
        for p in content_root.select("p"):
            text = p.get_text(" ", strip=True)
            if text:
                blocks.append(ParsedBlock(type="paragraph", text=text))

        # 6) 리스트 항목도 문단으로
        for li in content_root.select("ul li, ol li"):
            text = li.get_text(" ", strip=True)
            if text:
                blocks.append(ParsedBlock(type="paragraph", text=text, meta={"kind": "list-item"}))

        # 7) 테이블 캡션/요약 텍스트(필요 시)
        for cap in content_root.select("table caption"):
            text = cap.get_text(" ", strip=True)
            if text:
                blocks.append(ParsedBlock(type="paragraph", text=text, meta={"kind": "caption"}))

        # 8) 아무것도 못 뽑았으면 전체 텍스트
        if not blocks:
            page_text = content_root.get_text(" ", strip=True)
            if page_text:
                blocks.append(ParsedBlock(type="paragraph", text=page_text))

        return ParsedDocument(
            source=raw.source,
            title=title,
            blocks=blocks,
            lang=lang,
            meta={"block_count": len(blocks)},
            collection=raw.collection
        )