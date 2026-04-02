from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "LexMonitor Pro"
    app_version: str = "0.1.0"
    debug: bool = True


settings = Settings()