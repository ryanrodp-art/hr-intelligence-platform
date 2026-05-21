from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4o"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "hr_platform"
    postgres_user: str = "hr_user"
    postgres_password: str

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # FastAPI
    fastapi_host: str = "localhost"
    fastapi_port: int = 8000

    # Streamlit
    streamlit_port: int = 8501

    # MCP Server
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8002

    # DeepEval
    deepeval_api_key: str = ""

    # Application
    app_name: str = "ARIA - HR Intelligence Platform"
    app_env: str = "development"
    log_level: str = "INFO"

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"


# Singleton — import this instance throughout the app: from config.settings import settings
settings = Settings()
