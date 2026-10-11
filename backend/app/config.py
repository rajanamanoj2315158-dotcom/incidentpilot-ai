from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite:///./incidentpilot.db"
    sarvam_api_key: str | None = None
    sarvam_model: str = "sarvam-105b"
    sarvam_base_url: str = "https://api.sarvam.ai"
    agent_max_steps: int = 5
    approval_ttl_minutes: int = 30
    operator_token: str | None = None


settings = Settings()
