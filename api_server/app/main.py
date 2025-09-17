from __future__ import annotations
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from app.api.routers import health, search, extract, transform, load
from app.platform.config import settings
from app.platform.logging import setup_logging
from app.platform.errors import http_exception_handler, validation_exception_handler, unhandled_exception_handler
from app.middlewares.request_context import RequestContextMiddleware
from opensearchpy import OpenSearch


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
        # 필요 시 종료 처리
        try:
            app.state.opensearch.close()
        except Exception:
            pass

#setup_logging(log_to_file=True, log_dir="/var/log/app")
app = FastAPI(title="KReport API", lifespan=lifespan)
app.include_router(health.router)
app.include_router(extract.router, prefix="/api")
app.include_router(transform.router, prefix="/api")
app.include_router(load.router, prefix="/api")
app.include_router(search.router, prefix="/api")

# NestJS의 Global Exception Filter와 동일한 역할
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 요청 컨텍스트/액세스 로그 미들웨어
app.add_middleware(RequestContextMiddleware)

