from fastapi import APIRouter, Depends
from api_server.app.models.schemas import SearchRequest, SearchResponse, SearchHit
from api_server.app.platform.config import settings
from api_server.app.domain.services.opensearch_client import get_client
from api_server.app.security.guards import require_api_key

router = APIRouter(prefix="/load", tags=["load"], dependencies=[Depends(require_api_key)])

@router.post("", response_model=SearchResponse)
def load(req: SearchRequest):
    pass
