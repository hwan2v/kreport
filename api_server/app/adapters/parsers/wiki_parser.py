from __future__ import annotations
from typing import Sequence
from bs4 import BeautifulSoup

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

    MANDATORY_SELECTOR_KEY_DICT = {
        "infobox": "#mw-content-text > div.mw-content-ltr.mw-parser-output > table > tbody"
        #"body": "#mw-content-text > div.mw-content-ltr.mw-parser-output"
    }

    def parse(self, raw: RawDocument) -> ParsedDocument:
        html = raw.body_text or ""
        soup = BeautifulSoup(html, "lxml")

        blocks: list[ParsedBlock] = []

        # 1) title/lang
        title_tag = soup.select_one("h1") or soup.select_one("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        lang = (soup.html.get("lang") if soup.html else None) or None

        # 2) 불필요한 요소 제거
        for sel in self._STRIP_SELECTORS:
            for el in soup.select(sel):
                el.decompose()


        # 3) 필수 선택자 추출
        mandatory_result = {}
        for key, value in self.MANDATORY_SELECTOR_KEY_DICT.items():
            target = soup.select_one(value)
            if target:
                mandatory_result[key] = target.get_text(strip=True)
            else:
                mandatory_result[key] = None
        for key, value in mandatory_result.items():
            blocks.append(ParsedBlock(type=key, text=value))
        
        # 4) paragraph 선택 선택자 추출
        paragraph_result = {}
        # div.mw-heading.mw-heading2 각각 순회
        for div in soup.find_all("div", class_="mw-heading mw-heading2"):
            # div 안의 h2 텍스트를 key로 사용
            heading = div.find("h2").get_text(strip=True)
            if heading in ['각주', '외부 링크', '같이 보기', '관련 서적', '목차']:
                continue
            body = []
            # div 이후의 형제 태그들을 탐색
            for sibling in div.find_next_siblings():
                # 다음 heading div 만나면 멈춤
                if sibling.name == "div" and "mw-heading2" in sibling.get("class", []):
                    break
                # p 태그면 본문 수집
                if sibling.name == "p":
                    body.append(sibling.get_text(strip=True))
            paragraph_result[heading] = " ".join(body)
        
        paragraph_text = " ".join(paragraph_result.values())
        blocks.append(ParsedBlock(type="body", text=paragraph_text))

        # 5) summary 선택 선택자 추출
        summary_result = []
        container = soup.find("div", class_="mw-content-ltr mw-parser-output")
        table = container.find("table", class_="infobox vcard")
        if table:
            for sibling in table.find_next_siblings():
                # meta 태그 만나면 멈춤
                if sibling.name == "meta" and sibling.get("property") == "mw:PageProp/toc":
                    break
                # p 태그만 추출
                if sibling.name == "p":
                    text = sibling.get_text(strip=True)
                    if text:  # 빈 문단 제외
                        summary_result.append(text)
            summary_text = " ".join(summary_result)
            blocks.append(ParsedBlock(type="summary", text=summary_text))

        # 6) 아무것도 못 뽑았으면 전체 텍스트
        if not blocks:
            page_text = soup.get_text(" ", strip=True)
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