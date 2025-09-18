from opensearchpy import OpenSearch
from api_server.app.platform.config import settings

_client: OpenSearch | None = None

def get_client() -> OpenSearch:
    global _client
    if _client is None:
        _client = OpenSearch(hosts=[settings.OPENSEARCH_HOST])
    return _client

def close_client():
    global _client
    if _client:
        _client.Transport.close()
        _client = None
