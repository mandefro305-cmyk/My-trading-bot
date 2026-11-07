from pydantic_settings import BaseSettings
from typing import Optional, Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "GoldHunter AI"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    TRADING_MODE: Literal["PAPER", "EXNESS_DEMO", "EXNESS_REAL"] = "PAPER"
    LIVE_TRADING_ENABLED: bool = False
    EXNESS_CONFIRM_REAL_TRADING: bool = False
    SYMBOL: str = "XAUUSD"
    EXNESS_API_BASE_URL: str = "https://api.exness-trader.com"
    EXNESS_WS_EVENTS_URL: str = "wss://api.exness-trader.com"
    EXNESS_WS_TICKS_URL: str = "wss://api.exness-trader.com"
    EXNESS_API_KEY: str = ""
    EXNESS_PRIVATE_KEY_B64: str = ""
    EXNESS_ACCOUNT_ID: str = ""
    EXNESS_MOCK_MODE: bool = True
    XKIRO_BASE_URL: str = "https://api.xkiro.com/v1"
    XKIRO_API_KEY: str = ""
    XKIRO_PRIMARY_MODEL: str = "qwen/qwen3.7-max:free"
    XKIRO_FALLBACK_MODEL: str = "qwen/qwen3.7-flash:free"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_OWNER_ID: Optional[int] = None
    DATABASE_URL: str = "sqlite:///./goldhunter.db"
    MAX_RISK_PER_TRADE_PCT: float = 0.5
    MAX_DAILY_LOSS_PCT: float = 2.0
    MAX_TRADES_PER_DAY: int = 5
    MAX_CONSECUTIVE_LOSSES: int = 2
    MIN_RISK_REWARD: float = 2.0
    TP1_RR: float = 1.0
    TP1_CLOSE_PCT: float = 0.40
    TP2_RR: float = 2.0
    TP2_CLOSE_PCT: float = 0.30
    TP3_RR: float = 3.0
    TP3_CLOSE_PCT: float = 0.30
    NEWS_BLACKOUT_MINUTES_BEFORE: int = 30
    NEWS_BLACKOUT_MINUTES_AFTER: int = 30
    JWT_SECRET: str = "goldhunter-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    DASHBOARD_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
