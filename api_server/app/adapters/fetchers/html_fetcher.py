"""
file:// 경로나 로컬 경로에서 텍스트 파일을 읽는 FetchPort 구현체.
HTML/MD/TXT 등 확장자로 FileType을을 추정한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from api_server.app.domain.ports import FetchPort
from api_server.app.domain.models import RawDocument, SourceRef, FileType, Collection
from api_server.app.domain.utils import ext_to_file_type

class HtmlFetcher(FetchPort):
    """HTML 파일에서 문서를 읽어오는 구현체."""

    def __init__(self, default_encoding: str = "utf-8") -> None:
        self.default_encoding = default_encoding

    def fetch(self, uri: str, collection: Collection) -> RawDocument:
        """
        Args:
            uri: 'file:///abs/path.html' 또는 '/abs/path.html'
        """
        path_str = uri
        if uri.startswith("file://"):
            path_str = uri.replace("file://", "", 1)

        path = Path(path_str).expanduser().resolve()
        body_bytes = path.read_bytes()

        # 간단한 인코딩 추정: 실패시 기본 인코딩 사용
        try:
            body_text = body_bytes.decode(self.default_encoding)
            encoding = self.default_encoding
        except UnicodeDecodeError:
            body_text = body_bytes.decode("utf-8", errors="ignore")
            encoding = "utf-8"

        src = SourceRef(
            uri=uri,
            file_type=ext_to_file_type(path),
            headers=None,
        )
        return RawDocument(
            source=src,
            body_text=body_text,
            encoding=encoding,
            collection=collection
        )
