"""
file:// 경로나 로컬 경로에서 텍스트 파일 목록을을 읽는 ListenPort 구현체.
"""

from __future__ import annotations

import os
from typing import Optional, List
from api_server.app.domain.ports import ListenPort
from api_server.app.platform.exceptions import ResourceNotFound, PermissionDenied, DomainError

class FileListener(ListenPort):

    def listen(
        self, 
        source: str, 
        date: str, 
        extension: str, 
        base_dir: str = "api_server/resources/data") -> List[str]:
        resource_dir_path = self._create_resource_dir_path(source, date, base_dir)
        try:
            return [
                f'{resource_dir_path}/{filename}' \
                for filename in os.listdir(resource_dir_path) \
                if filename.endswith(extension)
            ]
        except FileNotFoundError as e:
            raise ResourceNotFound(f"Resource not found: {resource_dir_path} error={e}")
        except PermissionError as e:
            raise PermissionDenied(f"permission denied: {resource_dir_path} error={e}")
        except Exception as e:
            raise DomainError(f"failed to listen: {resource_dir_path} error={e}")
    
    def _create_resource_dir_path(
        self, 
        source: str, 
        date: str, 
        base_dir: str) -> str:
        return f"{base_dir}/{source}/day_{date}"