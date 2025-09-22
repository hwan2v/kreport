from __future__ import annotations
from pydantic import BaseModel
from pathlib import Path
import json
import os
from typing import Any, Dict

import logging
import traceback

from api_server.app.domain.ports import SearchPort
from api_server.app.domain.models import NormalizedChunk

logger = logging.getLogger(__name__)

class SearchService:

    def __init__(
        self,
        searcher: SearchPort) -> None:
        self._searcher = searcher
        
    # ================= public API =================
    def search(
        self, 
        query: str, 
        size: int = 3, 
        explain: bool = False) -> Dict[str, Any]:
        """
        검색을 수행하는 메서드.
        Args:
            query: str      : 검색 쿼리
            size: int       : 검색 결과 개수
            explain: bool   : 검색 결과 설명 포함 여부
        Returns:
            Any: 검색 결과
        """
        logger.info("service.search: query=%s size=%s explain=%s", query, size, explain)
        return self._searcher.search(query, size, explain)
