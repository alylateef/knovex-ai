from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    APP_NAME: str = "Knovex AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "knovex-super-secret-development-key-change-in-prod-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knovex_ai"
    DATABASE_SYNC_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knovex_ai"

    # Redis Cache & Rate Limiting
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant Vector Database
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "knovex_documents"

    # Model Cache Storage
    HF_HOME: Path = Path("D:/knovex-data/huggingface")
    FASTEMBED_CACHE_DIR: Path = Path("D:/knovex-data/fastembed")
    HUGGINGFACE_API_KEY: Optional[str] = Field(default=None, alias="HUGGINGFACE_API_KEY")

    # Dense Embeddings
    DENSE_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Sparse Embeddings (BM25 via FastEmbed)
    SPARSE_MODEL_NAME: str = "Qdrant/bm25"

    # Reranker
    ENABLE_RERANKER: bool = True
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_TOP_K: int = 5
    RETRIEVAL_CANDIDATE_LIMIT: int = 12

    # Primary LLM Configuration
    GROQ_API_KEY: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    GROQ_MODEL: str = "qwen/qwen3.8-27b"

    # Secondary LLM Configuration (Optional fallback)
    XAI_API_KEY: Optional[str] = Field(default=None, alias="XAI_API_KEY")
    GROK_MODEL: str = "grok-2-latest"
    GROK_TEMPERATURE: float = 0.0
    GROK_MAX_TOKENS: int = 512

    # Storage & Document Ingestion
    UPLOAD_DIR: Path = Path("./data/uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    # Tracing & Observability (LangSmith)
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "knovex-ai"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Synchronize LangSmith configuration to os.environ for LangChain/LangGraph runtime
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    return settings
