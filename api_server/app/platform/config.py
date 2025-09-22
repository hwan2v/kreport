from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from dotenv import load_dotenv
import os

class Settings(BaseSettings):
    APP_NAME: str = "k-report-api"
    DEBUG: bool = False

    OPENSEARCH_HOST: str = os.getenv('OPENSEARCH_HOST', 'http://1opensearch:9200')
    OPENSEARCH_INDEX: str = os.getenv('OPENSEARCH_INDEX', 'collection')
    OPENSEARCH_ALIAS: str = os.getenv('OPENSEARCH_ALIAS', 'kakaobank')

settings = Settings()
