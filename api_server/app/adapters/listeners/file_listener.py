"""
file:// 경로나 로컬 경로에서 텍스트 파일 목록을을 읽는 ListenPort 구현체.
"""

from __future__ import annotations

import os
from typing import Optional, List

from api_server.app.domain.ports import ListenPort

class FileListener(ListenPort):
    """로컬 파일에서 문서를 읽어오는 구현체."""

    def listen(self, source: str, date: str, extension: str) -> List[str]:
        resource_dir_path = self._create_resource_dir_path(source, date)
        return [
            f'{resource_dir_path}/{filename}' \
            for filename in os.listdir(resource_dir_path) \
            if filename.endswith(extension)
        ]
    
    def _create_resource_dir_path(self, source: str, date: str) -> str:
        return f"api_server/resources/data/{source}/day_{date}"