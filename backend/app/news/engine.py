import datetime
from typing import List, Dict, Any, Optional
from backend.app.config.settings import settings
from backend.app.database.session import SessionLocal
from backend.app.database.models import EconomicCalendar

class NewsEngine:
    def __init__(self):
        self.blackout_before = settings.NEWS_BLACKOUT_MINUTES_BEFORE
        self.blackout_after = settings.NEWS_BLACKOUT_MINUTES_AFTER

    def is_blackout_active(self, current_time: Optional[datetime.datetime] = None) -> tuple[bool, str]:
        if current_time is None:
            current_time = datetime.datetime.now(datetime.timezone.utc)
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
            return False, "No blackout active"
        finally:
            db.close()

    def get_upcoming_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            events = db.query(EconomicCalendar).order_by(EconomicCalendar.event_time.asc()).limit(limit).all()
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

    def populate_seed_events_if_empty(self):
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
        finally:
            db.close()
