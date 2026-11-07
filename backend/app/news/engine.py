import datetime
import logging
from typing import List, Dict, Any, Optional
from backend.app.config.settings import settings
from backend.app.database.session import SessionLocal
from backend.app.database.models import EconomicCalendar

logger = logging.getLogger(__name__)

class NewsEngine:
    def __init__(self):
        self.blackout_before = settings.NEWS_BLACKOUT_MINUTES_BEFORE
        self.blackout_after = settings.NEWS_BLACKOUT_MINUTES_AFTER
        self.in_memory_events: List[Dict[str, Any]] = [
            {
                "id": 1,
                "event_name": "US Non-Farm Payrolls (NFP)",
                "currency": "USD",
                "impact": "HIGH",
                "event_time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).isoformat(),
                "forecast": "180K"
            },
            {
                "id": 2,
                "event_name": "US CPI Inflation (YoY)",
                "currency": "USD",
                "impact": "HIGH",
                "event_time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)).isoformat(),
                "forecast": "3.1%"
            },
            {
                "id": 3,
                "event_name": "FOMC Interest Rate Decision",
                "currency": "USD",
                "impact": "HIGH",
                "event_time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12)).isoformat(),
                "forecast": "5.25%"
            }
        ]

    def is_blackout_active(self, current_time: Optional[datetime.datetime] = None) -> tuple[bool, str]:
        if current_time is None:
            current_time = datetime.datetime.now(datetime.timezone.utc)
        try:
            db = SessionLocal()
            try:
                window_start = current_time - datetime.timedelta(minutes=self.blackout_after)
                window_end = current_time + datetime.timedelta(minutes=self.blackout_before)
                events = db.query(EconomicCalendar).filter(
                    EconomicCalendar.currency == "USD",
                    EconomicCalendar.impact == "HIGH",
                    EconomicCalendar.event_time >= window_start,
                    EconomicCalendar.event_time <= window_end
                ).all()
                if events:
                    return True, f"High-impact news active: {events[0].event_name}"
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"DB unavailable for news blackout check, checking fallback: {e}")

        # Check in-memory fallback
        for ev in self.in_memory_events:
            if ev["impact"] == "HIGH" and ev["currency"] == "USD":
                try:
                    ev_time = datetime.datetime.fromisoformat(ev["event_time"])
                    if (current_time - datetime.timedelta(minutes=self.blackout_after)) <= ev_time <= (current_time + datetime.timedelta(minutes=self.blackout_before)):
                        return True, f"High-impact news active: {ev['event_name']}"
                except Exception:
                    pass

        return False, "No blackout active"

    def get_upcoming_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            db = SessionLocal()
            try:
                events = db.query(EconomicCalendar).order_by(EconomicCalendar.event_time.asc()).limit(limit).all()
                if events:
                    return [
                        {
                            "id": e.id,
                            "event_name": e.event_name,
                            "currency": e.currency,
                            "impact": e.impact,
                            "event_time": e.event_time.isoformat(),
                            "forecast": e.forecast
                        }
                        for e in events
                    ]
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"DB query failed for news, using in-memory events: {e}")

        return self.in_memory_events[:limit]

    def populate_seed_events_if_empty(self):
        try:
            db = SessionLocal()
            try:
                if db.query(EconomicCalendar).count() == 0:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    events = [
                        ("US Non-Farm Payrolls (NFP)", now + datetime.timedelta(days=2), "HIGH"),
                        ("US CPI Inflation (YoY)", now + datetime.timedelta(days=5), "HIGH"),
                        ("FOMC Interest Rate Decision", now + datetime.timedelta(days=12), "HIGH"),
                    ]
                    for name, dt, imp in events:
                        db.add(EconomicCalendar(event_name=name, currency="USD", impact=imp, event_time=dt, forecast="3.1%"))
                    db.commit()
                    logger.info("Economic calendar seeded with upcoming high-impact events.")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not populate seed news events in database: {e}")
