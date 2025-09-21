from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from api_server.app.platform.logging import request_id_ctx
import logging

def error_envelope(message, code="BAD_REQUEST", details=None, trace_id=None):
    return {"success": False, "error": {"code": code, "message": message, "details": details}, "trace_id": trace_id}

async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content=error_envelope(exc.detail, code=f"HTTP_{exc.status_code}", trace_id=request_id_ctx.get()))

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content=error_envelope(
                            "Validation failed", code="VALIDATION_ERROR", details=exc.errors(), 
                            trace_id=request_id_ctx.get()))

async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(status_code=500,
                        content=error_envelope(
                            "Internal server error", 
                            code="INTERNAL_ERROR", 
                            trace_id=request_id_ctx.get()))
