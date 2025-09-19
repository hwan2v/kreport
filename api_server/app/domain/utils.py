from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Iterable
from pydantic import BaseModel
import json

from api_server.app.domain.models import (
    ParsedBlock, ParsedDocument, SourceRef, FileType, Collection
)

def infer_date_from_path(source_path: str) -> datetime:
    part = source_path.split("/")[-2]
    days = int(part.split("_")[1])
    return datetime.now() - timedelta(days=days)


def ext_to_file_type(path: Path) -> FileType:
    ext = path.suffix.lower()
    if ext in {".html", ".htm"}:
        return FileType.html
    if ext in {".tsv"}:
        return FileType.tsv
    return FileType.plain


def choose_collection(ft: FileType) -> Collection:
    match ft:
        case FileType.html:
            return Collection.wiki
        case FileType.tsv:
            return Collection.qna
        case FileType.plain:
            return Collection.wiki
        case _:
            raise ValueError(f"Unsupported file type: {ft}")