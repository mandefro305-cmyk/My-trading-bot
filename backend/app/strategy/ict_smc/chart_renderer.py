import io
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict, Any, Optional

class ICTChartRenderer:
    """
    Renders dark-themed candlestick charts with Fair Value Gaps (FVGs),
    Liquidity Sweeps, and Entry / Stop Loss / Take Profit target levels.
    """

    @staticmethod
    def render_candlestick_chart(
        candles: List[Dict[str, Any]],
        symbol: str = "XAU/USD",
        timeframe: str = "M5",
        trade_setup: Optional[Dict[str, Any]] = None,
        fvgs: Optional[List[Dict[str, Any]]] = None
    ) -> io.BytesIO:
        if not candles:
            # Fallback mock candle data if empty
            candles = [
                {"open": 2900.0, "high": 2902.0, "low": 2899.0, "close": 2901.5}
                for _ in range(30)
            ]

        # Use last 35 candles
        slice_candles = candles[-35:]
        n = len(slice_candles)

        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        fig.patch.set_facecolor("#0b0e14")
        ax.set_facecolor("#11151f")

        # Plot candles
        for idx, c in enumerate(slice_candles):
            open_p = float(c["open"])
            high_p = float(c["high"])
            low_p = float(c["low"])
            close_p = float(c["close"])

            color = "#00e676" if close_p >= open_p else "#ff5252"

            # Wicks
            ax.plot([idx, idx], [low_p, high_p], color=color, linewidth=1.2, zorder=2)

            # Candle Body
            height = abs(close_p - open_p)
            bottom = min(open_p, close_p)
            # Ensure minimum height for doji
            if height == 0:
                height = 0.05
            rect = patches.Rectangle(
                (idx - 0.35, bottom),
                0.7,
                height,
                facecolor=color,
                edgecolor=color,
                zorder=3
            )
            ax.add_patch(rect)

        # Plot Fair Value Gaps (FVG)
        if fvgs:
            for fvg in fvgs[-3:]:
                top = float(fvg.get("top", 0.0))
                bot = float(fvg.get("bottom", 0.0))
                if top > bot:
                    fvg_color = "#3d5afe" if fvg.get("type") == "BULLISH_FVG" else "#ff9100"
                    ax.axhspan(bot, top, alpha=0.25, color=fvg_color, label=fvg.get("type", "FVG"))

        # Plot Trade Setup Overlay (Entry, SL, TP1, TP2)
        if trade_setup:
            entry = float(trade_setup.get("entry_price", 0.0))
            sl = float(trade_setup.get("stop_loss", 0.0))
            tp1 = float(trade_setup.get("tp1", trade_setup.get("take_profit_1", 0.0)))
            tp2 = float(trade_setup.get("tp2", trade_setup.get("take_profit_2", 0.0)))

            if entry > 0:
                ax.axhline(entry, color="#29b6f6", linestyle="--", linewidth=1.5, label=f"Entry: ${entry:.2f}")
            if sl > 0:
                ax.axhline(sl, color="#ff1744", linestyle="-.", linewidth=1.5, label=f"SL: ${sl:.2f}")
            if tp1 > 0:
                ax.axhline(tp1, color="#00e676", linestyle=":", linewidth=1.5, label=f"TP1: ${tp1:.2f}")
            if tp2 > 0:
                ax.axhline(tp2, color="#76ff03", linestyle=":", linewidth=1.5, label=f"TP2: ${tp2:.2f}")

        # Formatting
        ax.set_title(f"GoldHunter AI • {symbol} ({timeframe}) • ICT/SMC Structure", color="#ffffff", fontsize=13, fontweight="bold", pad=12)
        ax.grid(True, color="#212936", linestyle="--", alpha=0.6)
        ax.tick_params(colors="#90a4ae", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#263238")

        # Legend
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys(), facecolor="#161b26", edgecolor="#37474f", labelcolor="#cfd8dc", fontsize=8, loc="upper left")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf
