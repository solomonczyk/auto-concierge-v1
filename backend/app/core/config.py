from datetime import time
from pydantic_settings import BaseSettings
from typing import Optional
import secrets
import os
from urllib.parse import quote_plus

def generate_secret_key() -> str:
    """Generate a secure random secret key"""
    return secrets.token_urlsafe(32)

def get_env_secret_key() -> str:
    """Get SECRET_KEY from environment or generate one for development"""
    env_key = os.getenv("SECRET_KEY")
    if env_key and env_key != "dev-secret-key-change-in-production":
        return env_key
    # Generate a new key for development (will change on restart)
    # In production, this should always be set via environment variable
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("SECRET_KEY must be set in production environment!")
    return generate_secret_key()

def get_env_encryption_key() -> Optional[str]:
    """Get ENCRYPTION_KEY from environment"""
    key = os.getenv("ENCRYPTION_KEY")
    if key and key != "CHANGE_ME_USE_CRYPTOGRAPHY_FERNET_GENERATE_KEY":
        return key
    return None

class Settings(BaseSettings):
    PROJECT_NAME: str = "Autoservice MVP"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    
    TELEGRAM_BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE" # Placeholder, should be in .env

    SECRET_KEY: str = ""  # Will be set from environment or generated
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080 # 7 days for MVP comfort
    
    # Dedicated key for Fernet encryption of bot tokens (32 byte base64 encoded)
    ENCRYPTION_KEY: Optional[str] = None
    
    
    OPENAI_API_KEY: Optional[str] = None
    
    # GigaChat (Russian AI) settings
    GIGACHAT_CLIENT_ID: Optional[str] = None
    GIGACHAT_CLIENT_SECRET: Optional[str] = None
    
    WEBAPP_URL: str = "http://localhost:5173/webapp"
    
    @property
    def GIGACHAT_CREDENTIALS(self) -> Optional[str]:
        # Return the secret if it contains the full credentials string (base64)
        return self.GIGACHAT_CLIENT_SECRET

    # Telegram admin chat ID for notifications (set in .env)
    ADMIN_CHAT_ID: Optional[int] = None

    # Environment mode
    ENVIRONMENT: str = "development"

    # Working hours configuration
    WORK_START: int = 9  # Hour (0-23)
    WORK_END: int = 18   # Hour (0-23)
    SLOT_DURATION: int = 30  # Minutes

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{user}:{password}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def work_start_time(self) -> time:
        return time(self.WORK_START, 0)

    @property
    def work_end_time(self) -> time:
        return time(self.WORK_END, 0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set SECRET_KEY after initialization
        if not self.SECRET_KEY:
            self.SECRET_KEY = get_env_secret_key()
        if self.ENCRYPTION_KEY is None:
            self.ENCRYPTION_KEY = get_env_encryption_key()

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
