import pandas as pd
from typing import Dict, Any, List, Optional

class ICTSMCDetector:
    @staticmethod
    def identify_swing_points(df: pd.DataFrame, window: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        swing_highs = []
        swing_lows = []
        if len(df) < window * 2 + 1:
            return {"swing_highs": swing_highs, "swing_lows": swing_lows}

        has_time = "time" in df.columns

        for i in range(window, len(df) - window):
            high_val = df.iloc[i]["high"]
            low_val = df.iloc[i]["low"]
            candle_time = df.iloc[i]["time"] if has_time else i
            if high_val == df.iloc[i - window : i + window + 1]["high"].max():
                swing_highs.append({"index": i, "time": candle_time, "price": high_val})
            if low_val == df.iloc[i - window : i + window + 1]["low"].min():
                swing_lows.append({"index": i, "time": candle_time, "price": low_val})
        return {"swing_highs": swing_highs, "swing_lows": swing_lows}

    @staticmethod
    def detect_liquidity_sweeps(df: pd.DataFrame, swing_points: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        sweeps = []
        if len(df) < 2:
            return sweeps
        recent = df.iloc[-1]
        for sh in swing_points["swing_highs"][-5:]:
            if recent["high"] > sh["price"] and recent["close"] < sh["price"]:
                sweeps.append({"type": "BSL_SWEEP", "level": sh["price"], "direction": "SELL"})
        for sl in swing_points["swing_lows"][-5:]:
            if recent["low"] < sl["price"] and recent["close"] > sl["price"]:
                sweeps.append({"type": "SSL_SWEEP", "level": sl["price"], "direction": "BUY"})
        return sweeps

    @staticmethod
    def detect_fvg(df: pd.DataFrame) -> List[Dict[str, Any]]:
        fvgs = []
        if len(df) < 3:
            return fvgs
        for i in range(2, len(df)):
            c1 = df.iloc[i - 2]
            c3 = df.iloc[i]
            if c3["low"] > c1["high"]:
                fvgs.append({"type": "BULLISH_FVG", "top": c3["low"], "bottom": c1["high"]})
            elif c3["high"] < c1["low"]:
                fvgs.append({"type": "BEARISH_FVG", "top": c1["low"], "bottom": c3["high"]})
        return fvgs

    @staticmethod
    def detect_market_structure_shift(df: pd.DataFrame, swing_points: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        if len(df) < 3:
            return None
        recent_close = df.iloc[-1]["close"]
        shs = swing_points["swing_highs"]
        sls = swing_points["swing_lows"]
        if shs and recent_close > shs[-1]["price"]:
            return {"type": "BULLISH_MSS", "direction": "BUY"}
        elif sls and recent_close < sls[-1]["price"]:
            return {"type": "BEARISH_MSS", "direction": "SELL"}
        return None

    @staticmethod
    def calculate_premium_discount(high: float, low: float, current_price: float) -> Dict[str, Any]:
        equilibrium = (high + low) / 2.0
        zone = "PREMIUM" if current_price > equilibrium else "DISCOUNT"
        pct = ((current_price - low) / (high - low)) * 100.0 if high != low else 50.0
        return {"high": high, "low": low, "equilibrium": round(equilibrium, 2), "zone": zone, "percent": round(pct, 1)}
