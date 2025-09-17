# app/core/response.py
from app.core.logging import request_id_ctx

def ok(data=None, message="ok"):
    return {"success": True, "message": message, "data": data, "trace_id": request_id_ctx.get()}
