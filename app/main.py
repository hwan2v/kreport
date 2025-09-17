from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from app.api.routers import health, search
from app.core.logging import setup_logging
from app.core.errors import http_exception_handler, validation_exception_handler, unhandled_exception_handler
from app.middlewares.request_context import RequestContextMiddleware

setup_logging(log_to_file=True, log_dir="/var/log/app")
app = FastAPI(title="OpenSearch API")

# NestJS의 Global Exception Filter와 동일한 역할
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 요청 컨텍스트/액세스 로그 미들웨어
app.add_middleware(RequestContextMiddleware)

app.include_router(health.router)
#app.include_router(indexer.router)
app.include_router(search.router)
#app.include_router(reports.router)
