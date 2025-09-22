from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlparse
from opensearchpy import OpenSearch
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from api_server.app.api.routers import (
    health, 
    search, 
    extract, 
    transform, 
    index
)
from api_server.app.platform.config import settings
from api_server.app.platform.logging import setup_logging
from api_server.app.platform.errors import (
    http_exception_handler, 
    validation_exception_handler, 
    unhandled_exception_handler, 
    domain_exception_handler
)
from api_server.app.platform import exceptions as domainex
from api_server.app.middlewares.request_context import RequestContextMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    # 로깅 등 공통 준비
    setup_logging(log_to_file=True, log_dir="/var/log/app")

    # OpenSearch 클라이언트를 한 번만 생성해서 공유
    u = urlparse(settings.OPENSEARCH_HOST)
    app.state.opensearch = OpenSearch(
        hosts=[{"host": u.hostname, "port": u.port or 9200, "scheme": u.scheme or "http"}],
        verify_certs=False,
    )
    try:
        yield
    finally:
        try:
            app.state.opensearch.close()
        except Exception:
            pass

app = FastAPI(title="kakaobank Report API", lifespan=lifespan)
app.include_router(health.router)
app.include_router(extract.router, prefix="/api")
app.include_router(transform.router, prefix="/api")
app.include_router(index.router, prefix="/api")
app.include_router(search.router, prefix="/api")

# Global Exception Filter
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(domainex.DomainError, domain_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 요청 컨텍스트/액세스 로그 미들웨어
#app.add_middleware(RequestContextMiddleware)

