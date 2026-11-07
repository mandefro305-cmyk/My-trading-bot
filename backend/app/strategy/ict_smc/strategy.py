import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from backend.app.strategy.ict_smc.indicators import TechnicalIndicators
from backend.app.strategy.ict_smc.detector import ICTSMCDetector

class MultiTimeframeStrategyEngine:
    def __init__(self):
        self.detector = ICTSMCDetector()
        self.indicators = TechnicalIndicators()

    def analyze(
        self,
        h4_candles: List[Dict[str, Any]],
        h1_candles: List[Dict[str, Any]],
        m15_candles: List[Dict[str, Any]],
        m5_candles: List[Dict[str, Any]],
        current_bid: float,
        current_ask: float
    ) -> Optional[Dict[str, Any]]:
        if len(h4_candles) < 20 or len(h1_candles) < 20 or len(m15_candles) < 20 or len(m5_candles) < 20:
            return None

        df_h4 = self.indicators.enrich_candles(h4_candles)
        h4_close = df_h4.iloc[-1]["close"]
        h4_ema50 = df_h4.iloc[-1]["ema50"]

        df_h1 = self.indicators.enrich_candles(h1_candles)
        h1_high = df_h1["high"].tail(24).max()
        h1_low = df_h1["low"].tail(24).min()
        pd_zone = self.detector.calculate_premium_discount(h1_high, h1_low, current_bid)

        df_m15 = self.indicators.enrich_candles(m15_candles)
        m15_swings = self.detector.identify_swing_points(df_m15, window=3)
        m15_sweeps = self.detector.detect_liquidity_sweeps(df_m15, m15_swings)

        df_m5 = self.indicators.enrich_candles(m5_candles)
        m5_swings = self.detector.identify_swing_points(df_m5, window=3)
        m5_mss = self.detector.detect_market_structure_shift(df_m5, m5_swings)

        # Bullish setup check
        if pd_zone["zone"] == "DISCOUNT" and m5_mss and m5_mss["direction"] == "BUY":
            entry = current_ask
            lowest = df_m5.iloc[-5:]["low"].min()
            sl = round(lowest - 2.0, 2)
            dist = abs(entry - sl)
            if dist >= 1.5:
                return {
                    "direction": "BUY",
                    "symbol": "XAUUSD",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "tp1": round(entry + dist, 2),
                    "tp2": round(entry + 2 * dist, 2),
                    "tp3": round(entry + 3 * dist, 2),
                    "risk_reward": 2.0,
                    "context": {"pd_zone": "DISCOUNT"}
                }

        # Bearish setup check
        if pd_zone["zone"] == "PREMIUM" and m5_mss and m5_mss["direction"] == "SELL":
            entry = current_bid
            highest = df_m5.iloc[-5:]["high"].max()
            sl = round(highest + 2.0, 2)
            dist = abs(entry - sl)
            if dist >= 1.5:
                return {
                    "direction": "SELL",
                    "symbol": "XAUUSD",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "tp1": round(entry - dist, 2),
                    "tp2": round(entry - 2 * dist, 2),
                    "tp3": round(entry - 3 * dist, 2),
                    "risk_reward": 2.0,
                    "context": {"pd_zone": "PREMIUM"}
                }
        return None
