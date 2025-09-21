import sys
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가 (…/<project-root>)
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient
from api_server.app.main import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)
