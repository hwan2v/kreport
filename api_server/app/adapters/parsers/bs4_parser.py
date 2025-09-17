from __future__ import annotations
from typing import Sequence
from bs4 import BeautifulSoup

from app.domain.ports import ParsePort
from app.domain.models import ParsedDocument, ParsedBlock, RawDocument

class Bs4ArticleParser(ParsePort):
    """HTML에서 제목/문단을 뽑아 ParsedDocument로 변환."""
    def parse(self, raw: RawDocument) -> ParsedDocument:
        html = raw.body_text or ""
        soup = BeautifulSoup(html, "lxml")

        # title/lang 추출
        title_tag = soup.select_one("h1") or soup.select_one("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        lang = (soup.html.get("lang") if soup.html else None) or None

        blocks: list[ParsedBlock] = []
        # 우선순위: article p → 일반 p → (없으면 전체 텍스트 한 덩이)
        paras = soup.select("article p") or soup.select("p")
        for p in paras:
            text = p.get_text(" ", strip=True)
            if text:
                blocks.append(ParsedBlock(type="paragraph", text=text))

        if not blocks:
            page_text = soup.get_text(" ", strip=True)
            if page_text:
                blocks.append(ParsedBlock(type="paragraph", text=page_text))

        return ParsedDocument(source=raw.source, title=title, blocks=blocks, lang=lang, meta={})
