import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from backend.app.strategy.ict_smc.indicators import TechnicalIndicators
from backend.app.strategy.ict_smc.detector import ICTSMCDetector

logger = logging.getLogger("strategy")

class MultiTimeframeStrategyEngine:
    """
    ICT/SMC Multi-Timeframe Strategy Engine:
    - H4: Overall Market Context & Structural Bias (Price above/below EMA 50/200)
    - H1: Directional Bias & Premium/Discount Equilibrium Range
    - M15: Liquidity Sweep Identification (BSL / SSL Sweeps)
    - M5: Entry Confirmation (Market Structure Shift MSS + FVG / Displacement)
    """

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

        # 1. H4 Market Context: Trend alignment
        df_h4 = self.indicators.enrich_candles(h4_candles)
        h4_close = df_h4.iloc[-1]["close"]
        h4_ema50 = df_h4.iloc[-1].get("ema50", h4_close)
        h4_ema200 = df_h4.iloc[-1].get("ema200", h4_ema50)
        h4_bullish = h4_close >= h4_ema50
        h4_bearish = h4_close <= h4_ema50

        # 2. H1 Directional Bias & Premium/Discount Analysis
        df_h1 = self.indicators.enrich_candles(h1_candles)
        h1_high = df_h1["high"].tail(24).max()
        h1_low = df_h1["low"].tail(24).min()
        pd_zone = self.detector.calculate_premium_discount(h1_high, h1_low, current_bid)

        # 3. M15 Liquidity Sweep Detection
        df_m15 = self.indicators.enrich_candles(m15_candles)
        m15_swings = self.detector.identify_swing_points(df_m15, window=3)
        m15_sweeps = self.detector.detect_liquidity_sweeps(df_m15, m15_swings)
        recent_ssl_sweep = any(s.get("type") == "SSL_SWEEP" or s.get("sweep_type") == "SSL_SWEEP" for s in m15_sweeps[-5:]) if m15_sweeps else False
        recent_bsl_sweep = any(s.get("type") == "BSL_SWEEP" or s.get("sweep_type") == "BSL_SWEEP" for s in m15_sweeps[-5:]) if m15_sweeps else False

        # 4. M5 Entry Confirmation: Market Structure Shift & Displacement
        df_m5 = self.indicators.enrich_candles(m5_candles)
        m5_swings = self.detector.identify_swing_points(df_m5, window=3)
        m5_mss = self.detector.detect_market_structure_shift(df_m5, m5_swings)

        # BUY Setup: Bullish H4 + H1 Discount + (SSL sweep or Discount) + M5 Bullish MSS
        if h4_bullish and pd_zone["zone"] == "DISCOUNT" and (recent_ssl_sweep or pd_zone["discount_depth"] > 0.4):
            if m5_mss and m5_mss["direction"] == "BUY":
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
                        "context": {
                            "h4_bias": "BULLISH",
                            "pd_zone": pd_zone["zone"],
                            "ssl_swept": recent_ssl_sweep,
                            "mss_level": m5_mss["level"]
                        }
                    }

        # SELL Setup: Bearish H4 + H1 Premium + (BSL sweep or Premium) + M5 Bearish MSS
        if h4_bearish and pd_zone["zone"] == "PREMIUM" and (recent_bsl_sweep or pd_zone["premium_depth"] > 0.4):
            if m5_mss and m5_mss["direction"] == "SELL":
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
                        "context": {
                            "h4_bias": "BEARISH",
                            "pd_zone": pd_zone["zone"],
                            "bsl_swept": recent_bsl_sweep,
                            "mss_level": m5_mss["level"]
                        }
                    }

        return None
