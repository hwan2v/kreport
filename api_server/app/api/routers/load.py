from fastapi import APIRouter, Depends
from app.models.schemas import SearchRequest, SearchResponse, SearchHit
from app.core.config import settings
from app.services.opensearch_client import get_client
from app.security.guards import require_api_key

router = APIRouter(prefix="/load", tags=["load"], dependencies=[Depends(require_api_key)])

@router.post("", response_model=SearchResponse)
def load(req: SearchRequest):
    pass
