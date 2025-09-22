"""
HTML에서 제목/문단/리스트/헤딩 등 콘텐츠를 추출하여 ParsedDocument로 변환하는 구현체.
"""

from __future__ import annotations
from typing import List
from bs4 import BeautifulSoup
import re

from api_server.app.domain.ports import ParsePort
from api_server.app.domain.models import ParsedDocument, ParsedBlock, RawDocument

class WikiParser(ParsePort):

    # 위키에서 본문 외 요소 제거용 셀렉터
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
        HTML 텍스트를 읽어 필수 셀렉터 키를 추출하여 ParsedDocument로 변환한다.
        - 필수 셀렉터 키: infobox, paragraph, body, summary
        - 본문에 필수 셀렉터 키가 없으면 본문 전체를 body로 추출

        Args:
            raw: RawDocument (HTML 텍스트)
        Returns:
            ParsedDocument (제목/언어/infobox/summary/paragraph/body 블록)
        """
        html = raw.body_text or ""
        soup = BeautifulSoup(html, "lxml")

        blocks: List[ParsedBlock] = []

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
        
        # 필수 셀렉터 키가 없으면 본문 전체를 body로 추출
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
            불필요한 요소를 제거한다.
        Args:
            soup: BeautifulSoup
        """
        for sel in self._STRIP_SELECTORS:
            for el in soup.select(sel):
                el.decompose()

    def _parse_body_if_blocks_is_empty(
        self, 
        soup: BeautifulSoup,
        blocks: List[ParsedBlock]
    ) -> None:
        """
            아무것도 못 뽑았으면 전체 텍스트를 body로 추가한다.
        Args:
            soup: BeautifulSoup
            blocks: List[ParsedBlock]
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
        본문에서 해딩/문단/리스트/테이블 텍스트를 추출하여 body로 추가한다.

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
        infobox 텍스트를 추출하여 infobox로 추가한다.
        지정된 셀렉터에서 tbody 텍스트를 가져온다.

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
    ) -> ParsedBlock:
        """
        본문 최상단의 요약 텍스트를 추출하여 summary로 추가한다.

        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            List[ParsedBlock]
        """
        # 요약 영역 셀렉터 추출
        summary_result = []
        container = soup.find("div", class_=selector)
        if not container:
            return None
        table = container.find("table", class_="infobox vcard")
        if not table:
            return None

        # 요약 텍스트 추출
        for sibling in table.find_next_siblings():
            # meta 태그 만나면 멈춤
            if sibling.name == "meta" and sibling.get("property") == "mw:PageProp/toc":
                break
            # p 태그만 추출
            if sibling.name == "p":
                text = sibling.get_text()
                if text:
                    summary_result.append(text)
        
        summary_text = " ".join(summary_result)
        return ParsedBlock(type="summary", text=summary_text)

    def _parse_paragraph_from(
        self, 
        soup: BeautifulSoup, 
        selector: str, 
        filter_heading: list[str] = ['각주', '외부 링크', '같이 보기', '관련 서적', '목차']
    ) -> ParsedBlock:
        """
        본문에서 헤딩/문단 텍스트를 추출하여 paragraph로 추가한다.

        Args:
            soup: BeautifulSoup
            selector: str
        Returns:
            ParsedBlock
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