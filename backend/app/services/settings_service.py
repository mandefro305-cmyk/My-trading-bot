import logging
from typing import Dict, Any, Optional
from backend.app.database.session import SessionLocal
from backend.app.database.models import SystemSetting
from backend.app.config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "TRADING_MODE": settings.TRADING_MODE,
    "LIVE_TRADING_CONFIRMED": "false",
    "MAX_RISK_PER_TRADE_PCT": str(settings.MAX_RISK_PER_TRADE_PCT),
    "MAX_DAILY_LOSS_PCT": str(settings.MAX_DAILY_LOSS_PCT),
    "MAX_TRADES_PER_DAY": str(settings.MAX_TRADES_PER_DAY),
    "MAX_CONSECUTIVE_LOSSES": str(settings.MAX_CONSECUTIVE_LOSSES),
    "NEWS_BLACKOUT_MINUTES_BEFORE": str(settings.NEWS_BLACKOUT_MINUTES_BEFORE),
    "NEWS_BLACKOUT_MINUTES_AFTER": str(settings.NEWS_BLACKOUT_MINUTES_AFTER),
    "PAUSED": "false"
}

class SettingsService:
    @staticmethod
    def get_setting(key: str, default: Optional[str] = None) -> str:
        try:
            db = SessionLocal()
            try:
                row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
                if row:
                    return row.value
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not load setting {key} from DB: {e}")
        return default if default is not None else DEFAULT_SETTINGS.get(key, "")

    @staticmethod
    def set_setting(key: str, value: str, description: str = "") -> None:
        try:
            db = SessionLocal()
            try:
                row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
                if row:
                    row.value = str(value)
                    if description:
                        row.description = description
                else:
                    row = SystemSetting(key=key, value=str(value), description=description)
                    db.add(row)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not persist setting {key}={value} in DB: {e}")

    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        result = dict(DEFAULT_SETTINGS)
        try:
            db = SessionLocal()
            try:
                rows = db.query(SystemSetting).all()
                for r in rows:
                    result[r.key] = r.value
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Using default in-memory settings: {e}")

        return {
            "trading_mode": result.get("TRADING_MODE", "EXNESS_DEMO"),
            "live_confirmed": result.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true",
            "max_risk_pct": float(result.get("MAX_RISK_PER_TRADE_PCT", 0.5)),
            "max_daily_loss_pct": float(result.get("MAX_DAILY_LOSS_PCT", 2.0)),
            "max_trades_per_day": int(result.get("MAX_TRADES_PER_DAY", 5)),
            "max_consecutive_losses": int(result.get("MAX_CONSECUTIVE_LOSSES", 2)),
            "news_blackout_before": int(result.get("NEWS_BLACKOUT_MINUTES_BEFORE", 30)),
            "news_blackout_after": int(result.get("NEWS_BLACKOUT_MINUTES_AFTER", 30)),
            "paused": result.get("PAUSED", "false").lower() == "true"
        }
