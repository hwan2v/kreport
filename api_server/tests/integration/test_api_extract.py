# tests/integration/test_extract_api.py
from fastapi.testclient import TestClient
from api_server.app.main import app
from api_server.app.api import deps
from api_server.app.domain.services.search_service import SearchService

class FakeFetch:  # FetchPort
    def fetch(self, uri: str):
        from api_server.app.domain.models import RawDocument, SourceRef, FileType
        return RawDocument(source=SourceRef(uri=uri, file_type=FileType.html), body_text="<p>hello</p>")

class FakeParse:  # ParsePort
    def parse(self, raw):
        from api_server.app.domain.models import ParsedDocument, ParsedBlock
        return ParsedDocument(source=raw.source, title="T", blocks=[ParsedBlock(type="paragraph", text="hello")])

class FakeXform:  # TransformPort
    def to_chunks(self, doc, collection):
        from api_server.app.domain.models import NormalizedChunk
        yield NormalizedChunk(collection=collection, doc_id="doc_1", seq=0, title=doc.title, content="hello", url=doc.source.uri, lang=None)

class FakeIndexer:  # IndexPort
    def index(self, chunks):
        from api_server.app.domain.models import IndexResult
        return IndexResult(indexed=len(list(chunks)), errors=[])

def override_search_service():
    return SearchService(FakeFetch(), FakeParse(), FakeXform(), FakeIndexer())

def test_extract_ok():
    app.dependency_overrides[deps.get_search_service] = override_search_service

    client = TestClient(app)
    r = client.post("/api/extract", json={"source":"https://ex", "collection":"news"})
    assert r.status_code == 200
    assert r.json()["indexed"] == 1

    app.dependency_overrides.clear()
