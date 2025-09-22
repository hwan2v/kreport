"""
file:// 경로나 로컬 경로에서 텍스트 파일을 읽는 FetchPort 구현체.
"""

from __future__ import annotations

import os
from pathlib import Path

from api_server.app.domain.ports import FetchPort
from api_server.app.domain.models import RawDocument, SourceRef, FileType, Collection
from api_server.app.domain.utils import ext_to_file_type
from api_server.app.platform.exceptions import DomainError, InvalidInput, ResourceNotFound

class FileFetcher(FetchPort):
    def __init__(self, default_encoding: str = "utf-8") -> None:
        self.default_encoding = default_encoding

    def fetch(self, uri: str, collection: Collection) -> RawDocument:
        """
        로컬 파일(plain path 또는 file:// 스킴)에서 텍스트를 읽어 RawDocument로 반환한다.
        - 테스트/운영 OS에 상관없이 항상 같은 절대 경로 쓰기 위해 URI 정규화
        - 줄바꿈 정규화, 기본 인코딩 폴백 처리
        - 확장자 -> FileType 매핑으로 후속 파이프라인(파서/트랜스포머) 분기 정보 제공

        Args:
            uri: 'file:///abs/path.html' 또는 'abs/path.html'
            collection: Collection(wiki, qna)
        Returns:
            RawDocument: 원문(텍스트/바이트, 인코딩/메타 포함)
        """
        try:
            path = self._convert_uri_to_path(uri)
            if not path.exists():
                raise FileNotFoundError("File not found")
            body_bytes = path.read_bytes()

            try:
                body_text = body_bytes.decode(self.default_encoding)
                encoding = self.default_encoding
            except UnicodeDecodeError:
                body_text = body_bytes.decode("utf-8", errors="ignore")
                encoding = "utf-8"
            # 줄바꿈 정규화
            body_text = body_text.replace("\r\n", "\n").replace("\r", "\n")
            
            src = SourceRef(
                uri=uri,
                file_type=ext_to_file_type(path)
            )
            return RawDocument(
                source=src,
                body_text=body_text,
                encoding=encoding,
                collection=collection
            )
        except FileNotFoundError as e:
            raise ResourceNotFound(f"Resource not found: {uri} collection={collection} error={e}")
        except ValueError as e:
            raise InvalidInput(f"invalid input file type: {uri} collection={collection} error={e}")
        except Exception as e:
            raise DomainError(f"failed to fetch: {uri} collection={collection} error={e}")
    
    def _convert_uri_to_path(self, uri: str) -> Path:
        """
        상대 경로나 file:// prefix가 있는 경우 절대 경로로 변환한다.
        - file:// -> 실제 파일 경로 문자열로 변환
        - expanduser(): ~ (홈 디렉터리) 기호를 실제 경로로 확장
        - resolve(): 상대 경로, .. 등을 제거하고 절대 경로로 변환

        테스트/운영 환경에 따라 달라지는 문제 방지, 일관된 절대 경로를 제공

        Args:
            uri: 'file:///abs/path.html' 또는 '/abs/path.html'
        Returns:
            Path: 절대 경로
        """
        path_str = uri
        if uri.startswith("file://"):
            path_str = uri.replace("file://", "", 1)
        path = Path(path_str).expanduser().resolve()
        return path
