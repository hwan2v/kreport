import os
import tempfile
import textwrap
import pytest

from api_server.app.platform.config import Settings


def test_default_settings():
    """기본값이 올바르게 설정되는지 검증"""
    s = Settings()
    assert s.APP_NAME == "k-report-api"
    assert s.DEBUG is False
    assert s.OPENSEARCH_HOST.startswith("http://")
    assert s.STORAGE_BACKEND == "local"
    assert s.CELERY_BROKER_URL.startswith("redis://")


def test_override_with_env(monkeypatch):
    """환경변수로 설정값이 덮어써지는지 검증"""
    monkeypatch.setenv("APP_NAME", "custom-app")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("OPENSEARCH_HOST", "http://test:9999")

    s = Settings()
    assert s.APP_NAME == "custom-app"
    assert s.DEBUG is True
    assert s.OPENSEARCH_HOST == "http://test:9999"


def test_env_file_loading(tmp_path, monkeypatch):
    """env 파일에서 로딩되는지 검증"""
    env_file = tmp_path / ".env"
    env_file.write_text(textwrap.dedent("""
        APP_NAME=env-app
        DEBUG=true
        OPENSEARCH_HOST=http://env:1234
    """))

    monkeypatch.setenv("ENV_FILE", str(env_file))

    s = Settings(_env_file=env_file)
    assert s.APP_NAME == "env-app"
    assert s.DEBUG is True
    assert s.OPENSEARCH_HOST == "http://env:1234"


def test_s3_settings(monkeypatch):
    """S3 관련 설정이 주입되는지 검증"""
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("S3_BUCKET", "reports")
    monkeypatch.setenv("S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("S3_SECRET_KEY", "sk")

    s = Settings()
    assert s.STORAGE_BACKEND == "s3"
    assert s.S3_ENDPOINT == "http://minio:9000"
    assert s.S3_BUCKET == "reports"
    assert s.S3_ACCESS_KEY == "ak"
    assert s.S3_SECRET_KEY == "sk"
