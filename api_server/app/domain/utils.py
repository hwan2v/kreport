from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from pydantic import BaseModel
import json

from api_server.app.domain.models import ParsedBlock, ParsedDocument, SourceRef, FileType, Collection

def save_parsed_document(collection: str, docs: List[BaseModel] = None, out_dir: str = "./data"):
    # JSON 직렬화
    file_name = f"{collection}.json"
    out = Path(out_dir) / file_name
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False) + "\n")
    print(f"{file_name} 파일이 생성되었습니다.")
    return out.name

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