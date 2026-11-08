from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "GoldHunter AI"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Execution Mode: EXNESS_DEMO or EXNESS_REAL (paper staff removed)
    TRADING_MODE: Literal["EXNESS_DEMO", "EXNESS_REAL", "PAPER"] = "EXNESS_DEMO"
    LIVE_TRADING_CONFIRMED: bool = False

    SYMBOL: str = "XAUUSD"
    EXNESS_API_BASE_URL: str = "https://api.exness.com"
    EXNESS_API_ALT_BASE_URL: str = "https://api.exness-api.com"

    # Exness Demo Account Credentials
    EXNESS_DEMO_ACCOUNT_ID: str = ""
    EXNESS_DEMO_API_KEY: str = ""
    EXNESS_DEMO_PRIVATE_KEY_B64: str = ""
    EXNESS_DEMO_PRIVATE_SIGNING_KEY: str = ""

    # Exness Real Account Credentials
    EXNESS_REAL_ACCOUNT_ID: str = ""
    EXNESS_REAL_API_KEY: str = ""
    EXNESS_REAL_PRIVATE_KEY_B64: str = ""
    EXNESS_REAL_PRIVATE_SIGNING_KEY: str = ""

    # Shared Fallback Exness Credentials if user uses single key
    EXNESS_ACCOUNT_ID: str = ""
    EXNESS_API_KEY: str = ""
    EXNESS_PRIVATE_KEY_B64: str = ""
    EXNESS_PRIVATE_SIGNING_KEY: str = ""

    # AI Engine (xKiro)
    XKIRO_BASE_URL: str = "https://api.xkiro.com/v1"
    XKIRO_API_KEY: str = ""
    XKIRO_PRIMARY_MODEL: str = "qwen/qwen3.7-max:free"
    XKIRO_FALLBACK_MODEL: str = "qwen/qwen3.7-flash:free"

    # Telegram Control Center
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_OWNER_ID: Optional[int] = None

    # Database
    DATABASE_URL: str = "sqlite:///./goldhunter.db"

    # Dynamic Deterministic Risk Management Rules
    MAX_RISK_PER_TRADE_PCT: float = 0.5
    MAX_DAILY_LOSS_PCT: float = 2.0
    MAX_TRADES_PER_DAY: int = 5
    MAX_CONSECUTIVE_LOSSES: int = 2
    MIN_RISK_REWARD: float = 2.0

    # Structured 3-Stage Partial Profit Taking Rules
    TP1_RR: float = 1.0
    TP1_CLOSE_PCT: float = 0.40
    TP2_RR: float = 2.0
    TP2_CLOSE_PCT: float = 0.30
    TP3_RR: float = 3.0
    TP3_CLOSE_PCT: float = 0.30

    # News Blackout Rules
    NEWS_BLACKOUT_MINUTES_BEFORE: int = 30
    NEWS_BLACKOUT_MINUTES_AFTER: int = 30

    # Auth
    JWT_SECRET: str = "goldhunter-secret-key"
    DASHBOARD_PASSWORD: str = "admin123"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
