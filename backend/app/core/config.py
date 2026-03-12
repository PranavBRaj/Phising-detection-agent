from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or a .env file.
    All values can be overridden via environment variables (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = (
        "mysql+pymysql://fraud_user:your_secure_password@localhost:3306/fraud_detection"
    )

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    DEBUG: bool = False

    # CORS — comma-separated origin strings, e.g. "*" or "chrome-extension://abc,http://localhost:3000"
    ALLOWED_ORIGINS: str = "*"

    # URL analysis
    REQUEST_TIMEOUT: int = 10   # seconds per request
    MAX_REDIRECTS: int = 10     # maximum redirect hops to follow


settings = Settings()
