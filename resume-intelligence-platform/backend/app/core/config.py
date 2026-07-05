import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # LLM Settings
    LLM_PROVIDER: str = Field(default="gemini", validation_alias="LLM_PROVIDER")
    LLM_API_KEY: str = Field(default="mock_key_for_scaffolding", validation_alias="LLM_API_KEY")
    
    # Application settings
    MAX_UPLOAD_MB: int = Field(default=5, validation_alias="MAX_UPLOAD_MB")
    ENV: str = Field(default="development", validation_alias="ENV")
    PORT: int = Field(default=8000, validation_alias="PORT")
    HOST: str = Field(default="127.0.0.1", validation_alias="HOST")

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
