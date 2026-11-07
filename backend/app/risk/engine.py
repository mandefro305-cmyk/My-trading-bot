import math
from typing import Dict, Any, Tuple, Optional
from backend.app.config.settings import settings

class RiskEngine:
    def __init__(
        self,
        max_risk_pct: Optional[float] = None,
        max_daily_loss_pct: Optional[float] = None,
        max_trades_per_day: Optional[int] = None,
        max_consecutive_losses: Optional[int] = None
    ):
        self.max_risk_pct = (max_risk_pct if max_risk_pct is not None else settings.MAX_RISK_PER_TRADE_PCT) / 100.0
        self.max_daily_loss_pct = (max_daily_loss_pct if max_daily_loss_pct is not None else settings.MAX_DAILY_LOSS_PCT) / 100.0
        self.max_trades_per_day = max_trades_per_day if max_trades_per_day is not None else settings.MAX_TRADES_PER_DAY
        self.max_consecutive_losses = max_consecutive_losses if max_consecutive_losses is not None else settings.MAX_CONSECUTIVE_LOSSES
        self.min_risk_reward = settings.MIN_RISK_REWARD

        self.daily_starting_equity = 10000.0
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.consecutive_losses = 0
        self.manual_approval_required = False
        self.paused = False

    def can_open_new_trade(self) -> bool:
        if self.paused:
            return False
        if self.manual_approval_required:
            return False
        if self.daily_trade_count >= self.max_trades_per_day:
            return False
        current_loss_pct = abs(min(0.0, self.daily_pnl)) / max(1.0, self.daily_starting_equity)
        if current_loss_pct >= self.max_daily_loss_pct:
            return False
        return True

    def get_state(self) -> Dict[str, Any]:
        return {
            "max_risk_pct": round(self.max_risk_pct * 100.0, 2),
            "max_daily_loss_pct": round(self.max_daily_loss_pct * 100.0, 2),
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
            "can_trade": self.can_open_new_trade()
        }

    def calculate_position_size(self, equity: float, entry_price: float, stop_loss: float) -> Tuple[bool, float, str]:
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return False, 0.0, "Zero SL distance"
        risk_capital = equity * self.max_risk_pct
        risk_per_lot = (sl_distance + 0.3) * 100.0
        lots = round(math.floor((risk_capital / risk_per_lot) / 0.01) * 0.01, 2)
        return True, max(0.01, min(100.0, lots)), "Success"

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
