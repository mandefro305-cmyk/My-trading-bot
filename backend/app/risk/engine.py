import math
from typing import Dict, Any, Tuple
from backend.app.config.settings import settings

class RiskEngine:
    def __init__(self):
        self.max_risk_pct = settings.MAX_RISK_PER_TRADE_PCT / 100.0
        self.max_daily_loss_pct = settings.MAX_DAILY_LOSS_PCT / 100.0
        self.max_trades_per_day = settings.MAX_TRADES_PER_DAY
        self.max_consecutive_losses = settings.MAX_CONSECUTIVE_LOSSES
        self.min_risk_reward = settings.MIN_RISK_REWARD

        self.daily_starting_equity = 10000.0
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.consecutive_losses = 0
        self.manual_approval_required = False
        self.paused = False

    def get_state(self) -> Dict[str, Any]:
        return {
            "max_risk_pct": self.max_risk_pct * 100.0,
            "max_daily_loss_pct": self.max_daily_loss_pct * 100.0,
            "max_trades_per_day": self.max_trades_per_day,
            "max_consecutive_losses": self.max_consecutive_losses,
            "min_risk_reward": self.min_risk_reward,
            "daily_starting_equity": self.daily_starting_equity,
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_pct": round(abs(min(0.0, self.daily_pnl)) / max(1.0, self.daily_starting_equity) * 100.0, 2),
            "daily_trade_count": self.daily_trade_count,
            "consecutive_losses": self.consecutive_losses,
            "manual_approval_required": self.manual_approval_required,
            "paused": self.paused,
            "can_trade": not self.paused and not self.manual_approval_required
        }

    def sync_from_db(self, db_session=None):
        pass

    def calculate_position_size(self, equity: float, entry_price: float, stop_loss: float) -> Tuple[bool, float, str]:
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return False, 0.0, "Zero SL distance"
        risk_capital = equity * self.max_risk_pct
        risk_per_lot = (sl_distance + 0.3) * 100.0
        lots = round(math.floor((risk_capital / risk_per_lot) / 0.01) * 0.01, 2)
        return True, max(0.01, min(100.0, lots)), "Success"

    def validate_new_trade(self, equity: float, entry_price: float, stop_loss: float, take_profit: float) -> Tuple[bool, str]:
        if self.paused:
            return False, "Paused"
        if self.manual_approval_required:
            return False, "Manual approval required"
        return True, "Valid"

    def record_trade_result(self, pnl: float, db_session=None):
        self.daily_pnl += pnl
        self.daily_trade_count += 1
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.manual_approval_required = True
        else:
            self.consecutive_losses = 0

    def approve_resume(self, db_session=None) -> bool:
        self.manual_approval_required = False
        self.consecutive_losses = 0
        return True

    def deny_resume(self, db_session=None) -> bool:
        self.manual_approval_required = True
        self.paused = True
        return True
