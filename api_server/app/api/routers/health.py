from fastapi import APIRouter, Depends

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health():
    return {"ok": True}
