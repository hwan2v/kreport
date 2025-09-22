"""
유틸리티 함수.
"""

from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel
import json

from api_server.app.domain.models import (
    ParsedBlock, ParsedDocument, SourceRef, FileType, Collection
)

def infer_date_from_path(source_path: str) -> datetime:
    """
    파일 경로에서 날짜를 추출하는 함수.
    Args:
        source_path: str (파일 경로)
    Returns:
        datetime: 날짜
    """
    part = source_path.split("/")[-2]
    days = int(part.split("_")[1])
    return datetime.now() - timedelta(days=days)


def ext_to_file_type(path: Path) -> FileType:
    """
    파일 확장자자에서 파일 타입을 추출하는 함수.
    Args:
        path: Path (파일 경로)
    Returns:
        FileType: 파일 타입
    """
    ext = path.suffix.lower()
    if ext in {".html", ".htm"}:
        return FileType.html
    if ext in {".tsv"}:
        return FileType.tsv
    raise ValueError(f"Unsupported file type: {ext}")


def choose_collection(ft: FileType) -> Collection:
    """
    파일 타입에 따라 컬렉션을 선택하는 함수.
    Args:
        ft: FileType (파일 타입)
    Returns:
        Collection: 컬렉션
    """
    match ft:
        case FileType.html:
            return Collection.wiki
        case FileType.tsv:
            return Collection.qna
        case _:
            raise ValueError(f"Unsupported file type: {ft}")