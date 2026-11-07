import asyncio
import datetime
import random
import uuid
from typing import Dict, Any, List, Optional, Callable

class MockExnessGateway:
    def __init__(self, initial_balance: float = 10000.0, base_price: float = 2900.0):
        self.balance = initial_balance
        self.equity = initial_balance
        self.current_price = base_price
        self.spread = 0.25
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._price_task = None
        self.on_tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def get_bid_ask(self) -> Dict[str, float]:
        half = self.spread / 2.0
        return {
            "bid": round(self.current_price - half, 2),
            "ask": round(self.current_price + half, 2),
        }

    async def start(self):
        self.running = True
        self._price_task = asyncio.create_task(self._price_generator())

    async def stop(self):
        self.running = False
        if self._price_task:
            self._price_task.cancel()

    async def _price_generator(self):
        while self.running:
            try:
                delta = random.gauss(0, 0.25)
                self.current_price = round(self.current_price + delta, 2)
                prices = self.get_bid_ask()

                tick_data = {
                    "instrument": "XAUUSD",
                    "bid": prices["bid"],
                    "ask": prices["ask"],
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }

                for cb in self.on_tick_callbacks:
                    cb(tick_data)

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def get_candles(self, symbol: str = "XAUUSD", timeframe: str = "M5", count: int = 60) -> List[Dict[str, Any]]:
        candles = []
        now = datetime.datetime.now(datetime.timezone.utc)
        p = self.current_price - (count * 0.1)
        for i in range(count):
            t = now - datetime.timedelta(minutes=(count - i) * 5)
            o = p
            h = o + abs(random.gauss(0, 1.0))
            l = o - abs(random.gauss(0, 1.0))
            c = l + (h - l) * random.random()
            candles.append({
                "time": t.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2)
            })
            p = c
        return candles

    async def open_position(
        self,
        symbol: str,
        side: str,
        volume: str,
        stop_loss_price: Optional[str] = None,
        take_profit_price: Optional[str] = None
    ) -> Dict[str, Any]:
        pos_id = str(uuid.uuid4())[:8]
        prices = self.get_bid_ask()
        open_price = prices["ask"] if side.lower() == "buy" else prices["bid"]

        pos_data = {
            "id": pos_id,
            "symbol": symbol,
            "direction": side.lower(),
            "volume": float(volume),
            "original_volume": float(volume),
            "open_price": open_price,
            "stop_loss": float(stop_loss_price) if stop_loss_price else None,
            "take_profit": float(take_profit_price) if take_profit_price else None,
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "opened_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self.positions[pos_id] = pos_data
        return {"status": "filled", "order_id": pos_id, "position": pos_data}

    async def close_position(self, position_id: str, volume: Optional[str] = None):
        if position_id in self.positions:
            if volume:
                vol_to_close = float(volume)
                pos = self.positions[position_id]
                pos["volume"] = max(0.0, round(pos["volume"] - vol_to_close, 2))
                if pos["volume"] <= 0.001:
                    del self.positions[position_id]
            else:
                del self.positions[position_id]
        return {"status": "accepted"}
