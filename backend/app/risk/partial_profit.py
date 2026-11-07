import math
import logging
from typing import Dict, Any, List
from backend.app.config.settings import settings

logger = logging.getLogger("partial_profit_engine")

class PartialProfitEngine:
    def __init__(self):
        self.tp1_rr = settings.TP1_RR
        self.tp2_rr = settings.TP2_RR
        self.tp3_rr = settings.TP3_RR
        self.tp1_pct = settings.TP1_CLOSE_PCT
        self.tp2_pct = settings.TP2_CLOSE_PCT
        self.tp3_pct = settings.TP3_CLOSE_PCT

    def calculate_targets(self, entry_price: float, stop_loss: float, direction: str) -> Dict[str, float]:
        r = abs(entry_price - stop_loss)
        if direction.lower() == "buy":
            tp1 = round(entry_price + (self.tp1_rr * r), 2)
            tp2 = round(entry_price + (self.tp2_rr * r), 2)
            tp3 = round(entry_price + (self.tp3_rr * r), 2)
        else:
            tp1 = round(entry_price - (self.tp1_rr * r), 2)
            tp2 = round(entry_price - (self.tp2_rr * r), 2)
            tp3 = round(entry_price - (self.tp3_rr * r), 2)
        return {"tp1": tp1, "tp2": tp2, "tp3": tp3, "r_distance": r}

    def check_position(
        self,
        position: Dict[str, Any],
        current_bid: float,
        current_ask: float,
        volume_min: float = 0.01
    ) -> List[Dict[str, Any]]:
        actions = []
        direction = position.get("direction", "buy").lower()
        open_price = float(position.get("open_price", 0.0))
        stop_loss = float(position.get("stop_loss", 0.0))
        initial_vol = float(position.get("initial_volume") or position.get("original_volume") or position.get("volume", 0.01))
        current_vol = float(position.get("volume", initial_vol))

        current_price = current_bid if direction == "buy" else current_ask
        targets = self.calculate_targets(open_price, stop_loss, direction)

        # Stop loss check
        if direction == "buy" and stop_loss > 0 and current_bid <= stop_loss:
            actions.append({"action": "CLOSE_FULL", "reason": "STOP_LOSS", "exec_price": current_bid, "volume": current_vol})
            return actions
        elif direction == "sell" and stop_loss > 0 and current_ask >= stop_loss:
            actions.append({"action": "CLOSE_FULL", "reason": "STOP_LOSS", "exec_price": current_ask, "volume": current_vol})
            return actions

        # TP1 check (close 40%, move SL to BE)
        if not position.get("tp1_hit", False):
            hit = (direction == "buy" and current_bid >= targets["tp1"]) or (direction == "sell" and current_ask <= targets["tp1"])
            if hit:
                close_vol = max(volume_min, round(math.floor((initial_vol * self.tp1_pct) / volume_min) * volume_min, 2))
                actions.append({
                    "action": "CLOSE_PARTIAL",
                    "stage": "TP1",
                    "target_price": targets["tp1"],
                    "exec_price": current_price,
                    "volume": min(close_vol, current_vol),
                    "move_sl_to_be": True
                })

        # TP2 check (close 30%)
        elif not position.get("tp2_hit", False):
            hit = (direction == "buy" and current_bid >= targets["tp2"]) or (direction == "sell" and current_ask <= targets["tp2"])
            if hit:
                close_vol = max(volume_min, round(math.floor((initial_vol * self.tp2_pct) / volume_min) * volume_min, 2))
                actions.append({
                    "action": "CLOSE_PARTIAL",
                    "stage": "TP2",
                    "target_price": targets["tp2"],
                    "exec_price": current_price,
                    "volume": min(close_vol, current_vol),
                    "move_sl_to_be": False
                })

        # TP3 check (close remaining)
        elif not position.get("tp3_hit", False):
            hit = (direction == "buy" and current_bid >= targets["tp3"]) or (direction == "sell" and current_ask <= targets["tp3"])
            if hit:
                actions.append({
                    "action": "CLOSE_FULL",
                    "stage": "TP3",
                    "reason": "TAKE_PROFIT_3",
                    "target_price": targets["tp3"],
                    "exec_price": current_price,
                    "volume": current_vol
                })

        return actions
