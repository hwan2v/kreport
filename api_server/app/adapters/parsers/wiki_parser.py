"""
HTML에서 제목/문단/리스트/헤딩을 뽑아 ParsedDocument로 변환하는 구현체.
"""

from __future__ import annotations
from typing import Sequence
from bs4 import BeautifulSoup
import re

from api_server.app.domain.ports import ParsePort
from api_server.app.domain.models import ParsedDocument, ParsedBlock, RawDocument

class WikiParser(ParsePort):
    """HTML에서 제목/문단/리스트/헤딩을 뽑아 ParsedDocument로 변환."""

    # 위키, 블로그 등에서 본문 외 요소 제거용 셀렉터
    _STRIP_SELECTORS = [
        "script", "style", "noscript", "footer", "nav",
        "aside", ".toc", ".mw-references-wrap", "sup.reference",
        ".catlinks", ".navbox", ".metadata", ".hatnote", ".mw-editsection",
    ]

    # 필수 추출 셀렉터 딕셔너리
    _MANDATORY_SELECTOR_DICT = {
        "infobox": "#mw-content-text > div.mw-content-ltr.mw-parser-output > table > tbody",
        "paragraph": "mw-heading mw-heading2",
        "body": "#mw-content-text",
        "summary": "mw-content-ltr mw-parser-output"
    }

    def parse(self, raw: RawDocument) -> ParsedDocument:
        """
        Args:
            raw: RawDocument
        Returns:
            ParsedDocument
        """
        html = raw.body_text or ""
        soup = BeautifulSoup(html, "lxml")

        blocks: list[ParsedBlock] = []

        # title/lang
        title_tag = soup.select_one("h1") or soup.select_one("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        lang = (soup.html.get("lang") if soup.html else None) or None

        # 불필요한 요소 제거
        self._delete_unnecessary_elements(soup)
        
        # 필수 추출 셀렉터 딕셔너리에 따라 추출
        blocks.append(self._parse_infobox_from(soup, self._MANDATORY_SELECTOR_DICT["infobox"]))
        blocks.append(self._parse_summary_from(soup, self._MANDATORY_SELECTOR_DICT["summary"]))
        blocks.append(self._parse_paragraph_from(soup, self._MANDATORY_SELECTOR_DICT["paragraph"]))
        blocks.append(self._parse_body_from(soup, self._MANDATORY_SELECTOR_DICT["body"]))
        self._parse_body_if_blocks_is_empty(soup, blocks)
        blocks = [block for block in blocks if block is not None]
        
        return ParsedDocument(
            source=raw.source,
            title=title,
            blocks=blocks,
            lang=lang,
            meta={"block_count": len(blocks)},
            collection=raw.collection
        )

    def _delete_unnecessary_elements(self, soup: BeautifulSoup) -> None:
        """
        Args:
            soup: BeautifulSoup
        """
        for sel in self._STRIP_SELECTORS:
            for el in soup.select(sel):
                el.decompose()

    def _parse_body_if_blocks_is_empty(
        self, 
        soup: BeautifulSoup,
        blocks: list[ParsedBlock]
    ) -> None:
        """
            아무것도 못 뽑았으면 전체 텍스트를 body로 추가
        Args:
            soup: BeautifulSoup
            blocks: list[ParsedBlock]
        """
        if not blocks:
            page_text = soup.get_text(" ", strip=True)
            if page_text:
                blocks.append(ParsedBlock(type="body", text=page_text))

    def _parse_body_from(
        self, 
        soup: BeautifulSoup, 
        selector: str
    ) -> ParsedBlock:
        """
        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            ParsedBlock
        """
        contents = []
        content_root: Tag = soup.select_one("#mw-content-text") or soup.body or soup
        for h in content_root.select("h1, h2, h3, h4, h5, h6"):
            text = h.get_text(" ", strip=True)
            if text:
                contents.append(text)

        # 문단
        for p in content_root.select("p"):
            text = p.get_text()
            if text:
                contents.append(text)

        # 리스트 항목도 문단으로
        for li in content_root.select("ul li, ol li"):
            text = li.get_text(" ", strip=True)
            if text:
                contents.append(text)

        # 테이블 요약 텍스트
        for cap in content_root.select("table"):
            text = cap.get_text(" ", strip=True)
            if text:
                contents.append(text)
        body_text = " ".join(contents)
        return ParsedBlock(type="body", text=body_text)

    def _parse_infobox_from(
        self, 
        soup: BeautifulSoup, 
        selector: str
    ) -> ParsedBlock:
        """
        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            ParsedBlock
        """
        target = soup.select_one(selector)
        if target:
            return ParsedBlock(type="infobox", text=target.get_text(" ", strip=True))
        return None

    def _parse_summary_from(
        self, 
        soup: BeautifulSoup, 
        selector: str
    ) -> list[ParsedBlock]:
        """
        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            list[ParsedBlock]
        """
        # summary 선택 선택자 추출
        summary_result = []
        container = soup.find("div", class_=selector)
        table = container.find("table", class_="infobox vcard")
        if table:
            for sibling in table.find_next_siblings():
                # meta 태그 만나면 멈춤
                if sibling.name == "meta" and sibling.get("property") == "mw:PageProp/toc":
                    break
                # p 태그만 추출
                if sibling.name == "p":
                    text = sibling.get_text()
                    if text:  # 빈 문단 제외
                        summary_result.append(text)
            summary_text = " ".join(summary_result)
            return ParsedBlock(type="summary", text=summary_text)
        return None

    def _parse_paragraph_from(
        self, 
        soup: BeautifulSoup, 
        selector: str, 
        filter_heading: list[str] = ['각주', '외부 링크', '같이 보기', '관련 서적', '목차']
    ) -> list[ParsedBlock]:
        """
        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            list[ParsedBlock]
        """
        # paragraph 선택 선택자 추출
        paragraph_result = {}
        # div.mw-heading.mw-heading2 각각 순회
        for div in soup.find_all("div", class_=selector):
            # div 안의 h2 텍스트를 key로 사용
            heading = div.find("h2").get_text("", strip=True)
            if heading in filter_heading:
                continue
            body = []
            # div 이후의 형제 태그들을 탐색
            for sibling in div.find_next_siblings():
                # 다음 heading div 만나면 멈춤
                if sibling.name == "div" and "mw-heading2" in sibling.get("class", []):
                    break
                # p 태그면 본문 수집
                if sibling.name == "p":
                    body.append(sibling.get_text())
            paragraph_result[heading] = " ".join(body)
        
        paragraph_text = " ".join(paragraph_result.values())
        return ParsedBlock(type="paragraph", text=paragraph_text)