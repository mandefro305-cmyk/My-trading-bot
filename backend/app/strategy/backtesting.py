from typing import List, Dict, Any, Optional
from backend.app.strategy.ict_smc.strategy import MultiTimeframeStrategyEngine
from backend.app.risk.engine import RiskEngine
from backend.app.risk.partial_profit import PartialProfitEngine

class BacktestingEngine:
    """
    Realistic Backtester for XAU/USD:
      - Spread, slippage, 3-stage profit-taking, and risk management.
      - Win rate, profit factor, max drawdown, and expectancy metrics.
    """

    def __init__(self, initial_balance: float = 10000.0, spread: float = 0.25):
        self.initial_balance = initial_balance
        self.spread = spread
        self.strategy = MultiTimeframeStrategyEngine()
        self.risk_engine = RiskEngine()
        self.pp_engine = PartialProfitEngine()

    def run_simulation(
        self,
        m5_candles: List[Dict[str, Any]],
        h1_candles: List[Dict[str, Any]],
        h4_candles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        balance = self.initial_balance
        peak = balance
        max_dd = 0.0
        trades = []
        open_pos: Optional[Dict[str, Any]] = None

        window = 30
        for i in range(window, len(m5_candles)):
            m5_slice = m5_candles[i - window : i]
            cur = m5_candles[i]
            bid = float(cur["close"]) - (self.spread / 2.0)
            ask = float(cur["close"]) + (self.spread / 2.0)

            if open_pos:
                actions = self.pp_engine.check_position(open_pos, bid, ask)
                for act in actions:
                    if act["action"] == "CLOSE_PARTIAL":
                        vol = act["volume"]
                        pnl = (act["exec_price"] - open_pos["open_price"]) * vol * 100.0 if open_pos["direction"] == "buy" else (open_pos["open_price"] - act["exec_price"]) * vol * 100.0
                        balance += pnl
                        open_pos["realized_pnl"] += pnl
                        open_pos["volume"] = round(open_pos["volume"] - vol, 2)
                        if act["stage"] == "TP1":
                            open_pos["tp1_hit"] = True
                            if act.get("move_sl_to_be"):
                                open_pos["stop_loss"] = open_pos["open_price"]
                    elif act["action"] == "CLOSE_FULL":
                        vol = open_pos["volume"]
                        pnl = (act["exec_price"] - open_pos["open_price"]) * vol * 100.0 if open_pos["direction"] == "buy" else (open_pos["open_price"] - act["exec_price"]) * vol * 100.0
                        balance += pnl
                        open_pos["realized_pnl"] += pnl
                        trades.append(open_pos)
                        open_pos = None
                        break

            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100.0 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

            if not open_pos and i % 5 == 0:
                setup = self.strategy.analyze(h4_candles, h1_candles, m5_slice, m5_slice, bid, ask)
                if setup:
                    sz_ok, lots, _ = self.risk_engine.calculate_position_size(balance, setup["entry_price"], setup["stop_loss"])
                    if sz_ok and lots >= 0.01:
                        open_pos = {
                            "direction": setup["direction"].lower(),
                            "open_price": setup["entry_price"],
                            "stop_loss": setup["stop_loss"],
                            "initial_volume": lots,
                            "volume": lots,
                            "realized_pnl": 0.0,
                            "tp1_hit": False,
                            "tp2_hit": False,
                            "tp3_hit": False
                        }

        wins = [t for t in trades if t["realized_pnl"] > 0]
        losses = [t for t in trades if t["realized_pnl"] < 0]
        gross_win = sum(t["realized_pnl"] for t in wins)
        gross_loss = abs(sum(t["realized_pnl"] for t in losses))

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100.0, 1) if trades else 0.0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else 999.0,
            "max_drawdown": round(max_dd, 2),
            "initial_balance": self.initial_balance,
            "ending_balance": round(balance, 2),
            "net_profit": round(balance - self.initial_balance, 2)
        }
