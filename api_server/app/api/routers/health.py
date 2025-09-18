from fastapi import APIRouter, Depends
from api_server.app.security.guards import require_api_key

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health():
    return {"ok": True}
