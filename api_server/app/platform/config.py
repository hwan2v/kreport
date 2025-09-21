from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "k-report-api"
    DEBUG: bool = False

    OPENSEARCH_HOST: str = Field("http://localhost:9200", description="http://host:port")
    OPENSEARCH_INDEX: str = "collection"
    OPENSEARCH_ALIAS: str = "kakaobank"

    # 리포트 저장소(로컬 파일/MinIO/S3 중 선택)
    STORAGE_BACKEND: str = Field("local", description="local|s3")
    STORAGE_DIR: str = "./data/reports"      # local 용
    S3_ENDPOINT: str | None = None
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    model_config = ConfigDict(env_file=".env")

settings = Settings()
