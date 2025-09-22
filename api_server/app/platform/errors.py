from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import status
from api_server.app.platform.logging import request_id_ctx
from api_server.app.platform import exceptions as domainex
import logging

def error_envelope(message, code="BAD_REQUEST", details=None, trace_id=None):
    return {
        "success": False, 
        "error": {
            "code": code, "message": message, "details": details
        }, 
        "trace_id": trace_id
    }

async def http_exception_handler(request: Request, exc: HTTPException):
    # 4xx, 5xx 에러
    return JSONResponse(status_code=exc.status_code,
                        content=error_envelope(
                            exc.detail, 
                            code=f"HTTP_{exc.status_code}", 
                            trace_id=request_id_ctx.get()))

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 422 Unprocessable Entity
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        content=error_envelope(
                            "Unprocessable Entity", 
                            code="VALIDATION_ERROR", 
                            details=exc.errors(), 
                            trace_id=request_id_ctx.get()))

async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled exception")
    # 500 Internal server error
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content=error_envelope(
                            "Internal server error", 
                            code="INTERNAL_ERROR", 
                            trace_id=request_id_ctx.get()))

async def domain_exception_handler(request: Request, exc: domainex.DomainError):
    """
    도메인/유즈케이스 예외를 HTTP로 매핑.
    """
    if isinstance(exc, domainex.ResourceNotFound):
        http_status = status.HTTP_404_NOT_FOUND
        code = "NOT_FOUND"
    elif isinstance(exc, domainex.InvalidInput):
        http_status = status.HTTP_400_BAD_REQUEST
        code = "INVALID_INPUT"
    elif isinstance(exc, domainex.PermissionDenied):
        http_status = status.HTTP_403_FORBIDDEN
        code = "PERMISSION_DENIED"
    elif isinstance(exc, domainex.IndexingFailed):
        http_status = status.HTTP_502_BAD_GATEWAY
        code = "INDEXING_FAILED"
    else:
        http_status = status.HTTP_400_BAD_REQUEST
        code = "SERVICE_ERROR"

    logging.getLogger(__name__).warning(
        "Domain error: %s (%s) path=%s", exc, code, str(request.url)
    )
    return JSONResponse(
        status_code=http_status,
        content=error_envelope(
            str(exc), 
            code=code, 
            trace_id=request_id_ctx.get())
    )