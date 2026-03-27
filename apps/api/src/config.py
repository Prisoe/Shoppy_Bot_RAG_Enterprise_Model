from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AWS (kept for reference, not used for LLM)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # Anthropic API
    anthropic_api_key: str = ""
    llm_model_id: str = "claude-haiku-4-5-20251001"

    # LLM Tuning — adjustable per-org or via API
    llm_temperature: float = 0.3    # 0.0 = deterministic, 1.0 = creative
    llm_max_tokens: int = 2048       # max response length
    llm_top_k: int = 0               # 0 = disabled; >0 limits vocab sampling
    llm_top_p: float = 0.0           # 0.0 = disabled; nucleus sampling

    # Voyage AI embeddings
    voyage_api_key: str = "none"

    # Bedrock (code ready — plug in bucket + set USE_LOCAL_STORAGE=false)
    bedrock_llm_model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"

    # S3 storage (ready — set USE_LOCAL_STORAGE=false + S3_BUCKET_NAME to activate)
    s3_bucket_name: str = ""
    s3_prefix: str = "rag-docs/"
    use_local_storage: bool = True
    local_storage_path: str = "/tmp/rag-docs"

    # Database
    database_url: str = "postgresql+asyncpg://rag:ragpassword@postgres:5432/ragdb"
    database_url_sync: str = "postgresql://rag:ragpassword@postgres:5432/ragdb"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    api_key_header: str = "X-API-Key"
    default_org_api_key: str = "dev-api-key-change-in-prod"

    # Alerting
    alert_email_to: str = "prosperalabi7@gmail.com"
    alert_email_from: str = "prosperalabi7@gmail.com"
    gmail_app_password: str = ""

    # KB
    shopify_help_center_url: str = "https://help.shopify.com"
    shopify_scrape_enabled: bool = True
    shopify_scrape_max_pages: int = 500
    prompts_dir: str = "/app/prompts"
    evals_dir: str = "/app/evals"
    embed_dimensions: int = 1024
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieval: int = 8

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
