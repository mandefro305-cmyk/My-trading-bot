import React, { useState, useEffect } from "react";
import TradingViewChart from "./components/TradingViewChart";
import {
  Activity, Shield, TrendingUp, AlertTriangle, Play, Pause,
  RefreshCw, CheckCircle2, DollarSign, XCircle, Settings, Award
} from "lucide-react";

export default function App() {
  const [overview, setOverview] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [news, setNews] = useState([]);
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showRealModal, setShowRealModal] = useState(false);

  const fetchData = async () => {
    try {
      const [ovRes, posRes, trRes, nwRes, cdRes] = await Promise.all([
        fetch("/api/v1/dashboard/overview"),
        fetch("/api/v1/positions"),
        fetch("/api/v1/trades"),
        fetch("/api/v1/news"),
        fetch("/api/v1/candles?timeframe=M5&count=50")
      ]);
      if (ovRes.ok) setOverview(await ovRes.json());
      if (posRes.ok) setPositions(await posRes.json());
      if (trRes.ok) setTrades(await trRes.json());
      if (nwRes.ok) setNews(await nwRes.json());
      if (cdRes.ok) {
        const rawCandles = await cdRes.json();
        const now = Math.floor(Date.now() / 1000);
        const mapped = rawCandles.map((c, idx) => ({
          time: c.time || (now - (rawCandles.length - idx) * 300),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close
        }));
        setCandles(mapped);
      }
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleControl = async (action, extra = {}) => {
    setActionLoading(true);
    try {
      await fetch("/api/v1/controls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...extra })
      });
      await fetchData();
    } catch (e) {
      console.error("Control action error:", e);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950 text-white font-mono">
        <RefreshCw className="w-8 h-8 animate-spin text-amber-500 mr-3" />
        Connecting to GoldHunter AI Backend...
      </div>
    );
  }

  const isReal = overview?.trading_mode === "EXNESS_REAL";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header Bar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <Award className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">GoldHunter AI</h1>
              <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-slate-800 text-amber-400 border border-amber-500/20">
                v2.0
              </span>
            </div>
            <p className="text-xs text-slate-400">Institutional XAU/USD Multi-Timeframe Trading Engine</p>
          </div>
        </div>

        {/* Mode Selector & Status */}
        <div className="flex items-center space-x-3">
          <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center space-x-2 ${
            isReal
              ? "bg-red-500/10 border-red-500/40 text-red-400 animate-pulse"
              : "bg-amber-500/10 border-amber-500/40 text-amber-400"
          }`}>
            <span className={`w-2 h-2 rounded-full ${isReal ? "bg-red-400" : "bg-amber-400"}`} />
            <span>{isReal ? "EXNESS REAL ACCOUNT" : "EXNESS DEMO ACCOUNT"}</span>
          </div>

          {/* Mode Switch Buttons */}
          {isReal ? (
            <button
              onClick={() => handleControl("set_mode", { mode: "EXNESS_DEMO" })}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
            >
              Switch to Demo
            </button>
          ) : (
            <button
              onClick={() => setShowRealModal(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 font-semibold"
            >
              Switch to Real
            </button>
          )}

          {/* Pause / Resume Controls */}
          {overview?.paused ? (
            <button
              onClick={() => handleControl("resume")}
              disabled={actionLoading}
              className="flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Resume</span>
            </button>
          ) : (
            <button
              onClick={() => handleControl("pause")}
              disabled={actionLoading}
              className="flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium"
            >
              <Pause className="w-3.5 h-3.5" />
              <span>Pause</span>
            </button>
          )}

          <button
            onClick={() => handleControl("closeall")}
            disabled={actionLoading}
            className="flex items-center space-x-1 text-xs px-3 py-1.5 rounded-lg bg-red-950/80 hover:bg-red-900 border border-red-700/50 text-red-200 font-medium"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Close All</span>
          </button>
        </div>
      </header>

      {/* Main Content Grid */}
      <main className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Exness Balance</span>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              ${overview?.balance?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || "10,000.00"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Equity: <span className="font-mono text-slate-200">${overview?.equity?.toFixed(2)}</span>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Today's P&L</span>
            <div className={`text-2xl font-bold font-mono mt-1 ${
              (overview?.daily_pnl || 0) >= 0 ? "text-emerald-400" : "text-rose-400"
            }`}>
              {overview?.daily_pnl >= 0 ? "+" : ""}${overview?.daily_pnl?.toFixed(2) || "0.00"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Loss: {overview?.daily_loss_pct || 0}% / Max {overview?.max_daily_loss_pct || 2}%
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Daily Trades</span>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {overview?.daily_trades || 0} <span className="text-xs text-slate-500 font-normal">/ {overview?.max_daily_trades || 5}</span>
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Consecutive Losses: <span className="font-mono text-amber-400">{overview?.consecutive_losses || 0} / 2</span>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">XAU/USD Live Quote</span>
            <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
              {overview?.current_bid?.toFixed(2) || "2900.00"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Spread: <span className="font-mono text-slate-200">${overview?.spread?.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Live Chart & AI Analysis */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-amber-400" />
                <h3 className="font-semibold text-sm">XAU/USD Market View</h3>
              </div>
              <span className="text-xs font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-400">5-Minute Candles</span>
            </div>
            <TradingViewChart candles={candles} />
          </div>

          {/* AI Consensus Panel */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center space-x-2 mb-3">
                <Activity className="w-4 h-4 text-indigo-400" />
                <h3 className="font-semibold text-sm">xKiro AI Market Consensus</h3>
              </div>
              <div className="space-y-3">
                <div className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                  <div className="text-xs text-slate-400">Current Direction Bias</div>
                  <div className="text-lg font-bold text-amber-400 mt-0.5">
                    {overview?.last_ai_analysis?.trading_bias || "Evaluating"}
                  </div>
                </div>
                <div className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                  <div className="text-xs text-slate-400">Confidence Score</div>
                  <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">
                    {Math.round((overview?.last_ai_analysis?.confidence_score || 0.85) * 100)}%
                  </div>
                </div>
                <div className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg">
                  <div className="text-xs text-slate-400 mb-1">Reasoning & Institutional Levels</div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {overview?.last_ai_analysis?.reason || "Institutional order block test and liquidity sweep observed on lower timeframes."}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span>Model: qwen3.7-max</span>
              <span className="text-emerald-400 flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Active
              </span>
            </div>
          </div>
        </div>

        {/* Open Positions Table */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm">Active Exness Positions ({positions.length})</h3>
            <span className="text-xs text-slate-400">Managed by 3-Stage Partial Profit Engine</span>
          </div>
          {positions.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500 font-mono">
              No active positions on Exness. System scanning for high-probability setups...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2">ID</th>
                    <th>Direction</th>
                    <th>Volume</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>TP1</th>
                    <th>TP2</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {positions.map(p => (
                    <tr key={p.id}>
                      <td className="py-2.5 text-slate-300 font-semibold">#{p.id}</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.direction === "buy" ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"
                        }`}>
                          {p.direction.toUpperCase()}
                        </span>
                      </td>
                      <td>{p.volume} lots</td>
                      <td>{p.open_price?.toFixed(2)}</td>
                      <td className="text-rose-400">{p.stop_loss?.toFixed(2)}</td>
                      <td className="text-emerald-400">{p.take_profit_1?.toFixed(2)}</td>
                      <td className="text-emerald-400">{p.take_profit_2?.toFixed(2)}</td>
                      <td>
                        <button
                          onClick={() => handleControl("closeall")}
                          className="px-2 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[10px]"
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Confirmation Modal for Live Real Trading */}
      {showRealModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-red-500/50 rounded-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center space-x-3 text-red-400">
              <AlertTriangle className="w-7 h-7" />
              <h3 className="text-lg font-bold">Switch to EXNESS REAL</h3>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              You are about to switch execution to your <b>Exness Real Live Account</b>.
              Real money will be used for market orders. Deterministic risk controls (0.5% max risk, 2% daily loss lock) will remain actively enforced.
            </p>
            <div className="flex justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowRealModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleControl("set_mode", { mode: "EXNESS_REAL", confirm_real: true });
                  setShowRealModal(false);
                }}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white"
              >
                Yes, Activate Real Trading
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
