from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./.data/zeroi.db"

    artifact_backend: str = "local"
    artifact_local_dir: str = ".data/artifacts"

    s3_endpoint: str = ""
    s3_bucket: str = "zeroi-artifacts"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen3-max"

    qwen_ui_agent_url: str = "http://localhost:8010"
    qwen_ui_agent_api_key: str = ""
    qwen_timeout: int = 180

    cli_sandbox_mode: str = "subprocess"
    cli_allowlist: str = "ls,cat,mkdir,cp,mv,rm,zip,unzip,convert,ffmpeg,pandoc,git,python,echo,pwd,find,grep,jq"

    browser_headless: bool = True

    search_provider: str = "searxng"
    searxng_url: str = "http://localhost:8080"
    serper_api_key: str = ""

    auth_disabled: bool = True
    zeroi_api_key: str = "dev-key"

    otel_endpoint: str = ""

    @property
    def cli_allowlist_list(self) -> list[str]:
        return [x.strip() for x in self.cli_allowlist.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
