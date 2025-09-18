import time, uuid, logging
from starlette.middleware.base import BaseHTTPMiddleware
from api_server.app.platform.logging import request_id_ctx

access_logger = logging.getLogger("uvicorn.access")

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            ms = (time.perf_counter() - start) * 1000
            #access_logger.info("%s %s %s %.2fms", request.method, request.url.path, getattr(response, "status_code", 500), ms)
            access_logger.info("%s %s %.2fms", request.method, request.url.path, ms)
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
