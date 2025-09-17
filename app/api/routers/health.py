from fastapi import APIRouter, Depends
from app.security.guards import require_api_key

router = APIRouter(prefix="/health", tags=["health"], dependencies=[Depends(require_api_key)])

@router.get("")
def health():
    return {"ok": True}
