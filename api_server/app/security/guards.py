from fastapi import Header, HTTPException, status
from api_server.app.platform.config import settings

def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    if not x_api_key or x_api_key != getattr(settings, "API_KEY", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid API key")
