from fastapi import APIRouter, Depends
from api_server.app.models.schemas import SearchRequest, SearchResponse, SearchHit
from api_server.app.platform.config import settings
from api_server.app.domain.services.opensearch_client import get_client
from api_server.app.security.guards import require_api_key

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(require_api_key)])

@router.post("", response_model=SearchResponse)
def search(req: SearchRequest):
    client = get_client()
    body = {
        "query": {"query_string": {"query": req.q}} if req.q != "*" else {"match_all": {}},
        "size": req.size
    }
    res = client.search(index=settings.OPENSEARCH_INDEX, body=body)
    hits = [
        SearchHit(_id=h["_id"], _score=h.get("_score"), source=h["_source"])
        for h in res["hits"]["hits"]
    ]
    return SearchResponse(hits=hits)

@router.get('/temp')
def temp():
    return {"message": "Hello, World!"}
