import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  ShieldAlert,
  TrendingUp,
  Pause,
  Play,
  CheckCircle,
  Clock,
  DollarSign,
  Activity,
  Bot
} from 'lucide-react';
import TradingViewChart from './components/TradingViewChart';

const API_BASE = 'http://localhost:8000/api/v1';

export default function App() {
  const [overview, setOverview] = useState(null);
  const [positions, setPositions] = useState([]);
  const [candles, setCandles] = useState([]);
  const [news, setNews] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchData = async () => {
    try {
      const [ovRes, posRes, cdRes, nwRes] = await Promise.all([
        axios.get(`${API_BASE}/dashboard/overview`),
        axios.get(`${API_BASE}/positions`),
        axios.get(`${API_BASE}/candles?timeframe=M5&count=60`),
        axios.get(`${API_BASE}/news`)
      ]);
      setOverview(ovRes.data);
      setPositions(posRes.data);
      setCandles(cdRes.data);
      setNews(nwRes.data);
    } catch (err) {
      console.error("Data fetch error:", err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleControl = async (action) => {
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE}/controls`, { action });
      await fetchData();
    } catch (err) {
      alert("Failed action: " + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-500 to-yellow-300 flex items-center justify-center shadow-lg shadow-amber-500/20">
            <Bot className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <h1 className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-amber-200 to-yellow-400 bg-clip-text text-transparent">
              GoldHunter AI <span className="text-xs text-slate-400 font-medium">v2.0</span>
            </h1>
            <p className="text-[11px] text-slate-400">Institutional XAU/USD Automated Trading Platform</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="px-3 py-1 rounded-full text-xs font-semibold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
            {overview?.trading_mode ? overview.trading_mode.replace('_', ' ') : 'PAPER TRADING'}
          </span>

          <div className="flex items-center gap-2">
            {overview?.paused ? (
              <button
                onClick={() => handleControl('resume')}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-medium text-white transition shadow-sm"
              >
                <Play className="w-3.5 h-3.5" /> Resume Trading
              </button>
            ) : (
              <button
                onClick={() => handleControl('pause')}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-xs font-medium text-white transition shadow-sm"
              >
                <Pause className="w-3.5 h-3.5" /> Pause Trading
              </button>
            )}

            <button
              onClick={() => handleControl('closeall')}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-red-400 border border-red-500/30 transition"
            >
              Close All
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs uppercase tracking-wider font-semibold">Account Equity</span>
              <DollarSign className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-slate-100">
              ${overview ? overview.equity.toFixed(2) : '10,000.00'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Starting: ${overview?.balance?.toFixed(2) || '10,000.00'}
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs uppercase tracking-wider font-semibold">Daily P&L</span>
              <Activity className="w-4 h-4 text-amber-400" />
            </div>
            <div className={`text-2xl font-bold tracking-tight ${overview?.daily_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {overview?.daily_pnl >= 0 ? '+' : ''}${overview?.daily_pnl?.toFixed(2) || '0.00'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Limit: -2.0% (Current: {overview?.daily_loss_pct || 0}%)
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs uppercase tracking-wider font-semibold">XAU/USD Live Price</span>
              <TrendingUp className="w-4 h-4 text-yellow-400" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-amber-300">
              ${overview?.current_bid ? overview.current_bid.toFixed(2) : '2,900.00'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Spread: {overview?.spread || 0.25} | Ask: ${overview?.current_ask?.toFixed(2) || '2,900.25'}
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 mb-1">
              <span className="text-xs uppercase tracking-wider font-semibold">Consecutive Losses</span>
              <ShieldAlert className="w-4 h-4 text-red-400" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-slate-100">
              {overview?.consecutive_losses || 0} <span className="text-sm font-normal text-slate-400">/ 2 max</span>
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Daily Trades: {overview?.daily_trades || 0} / 5 max
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <TradingViewChart candles={candles} height={380} />
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
                <Bot className="w-4 h-4 text-amber-400" />
                <h3 className="font-semibold text-sm text-slate-200">xKiro AI Engine Analysis</h3>
              </div>

              {overview?.last_ai_analysis ? (
                <div className="mt-4 space-y-3 text-xs">
                  <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400">Market Bias:</span>
                    <span className="font-bold text-amber-300">{overview.last_ai_analysis.trading_bias}</span>
                  </div>

                  <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400">AI Confidence:</span>
                    <span className="font-bold text-emerald-400">
                      {(overview.last_ai_analysis.confidence_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1.5">
                    <span className="text-slate-400 font-semibold block">Strategic Reasoning:</span>
                    <p className="text-slate-300 leading-relaxed text-[11px]">
                      {overview.last_ai_analysis.reason}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="mt-8 text-center text-slate-500 text-xs">
                  Analyzing market structure...
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <span>Primary: qwen/qwen3.7-max:free</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Active
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-sm text-slate-200 mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              Active Positions ({positions.length})
            </h3>
            {positions.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No open positions. Scanner actively tracking liquidity sweeps.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-slate-400 uppercase border-b border-slate-800">
                    <tr>
                      <th className="pb-2">Side</th>
                      <th className="pb-2">Lots</th>
                      <th className="pb-2">Open Price</th>
                      <th className="pb-2">Stop Loss</th>
                      <th className="pb-2">Target</th>
                      <th className="pb-2">PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {positions.map((pos) => (
                      <tr key={pos.position_id}>
                        <td className="py-2.5 font-bold uppercase text-emerald-400">{pos.direction}</td>
                        <td className="py-2.5">{pos.volume}</td>
                        <td className="py-2.5">${pos.open_price.toFixed(2)}</td>
                        <td className="py-2.5 text-red-400">${pos.stop_loss.toFixed(2)}</td>
                        <td className="py-2.5 text-emerald-400">${pos.take_profit.toFixed(2)}</td>
                        <td className="py-2.5 font-semibold text-emerald-400">
                          ${pos.unrealized_pnl?.toFixed(2) || '0.00'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold text-sm text-slate-200 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              USD Economic Calendar
            </h3>
            <div className="space-y-3">
              {news.slice(0, 3).map((item) => (
                <div key={item.id} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-slate-200">{item.event_name}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-red-500/20 text-red-400 font-bold border border-red-500/30">
                      {item.impact}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 flex items-center justify-between">
                    <span>{new Date(item.event_time).toLocaleDateString()}</span>
                    <span>Forecast: {item.forecast || 'N/A'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
