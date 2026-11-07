import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';

export default function TradingViewChart({ candles = [], height = 380 }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#090d16' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#172033' },
        horzLines: { color: '#172033' },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // In lightweight-charts v5: chart.addSeries(CandlestickSeries, options)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    if (candles && candles.length > 0) {
      const formatted = candles.map((c) => ({
        time: Math.floor(new Date(c.time).getTime() / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })).sort((a, b) => a.time - b.time);

      const unique = [];
      const seen = new Set();
      for (const item of formatted) {
        if (!seen.has(item.time)) {
          seen.add(item.time);
          unique.push(item);
        }
      }
      candlestickSeries.setData(unique);
    }

    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles, height]);

  return (
    <div className="w-full relative rounded-xl overflow-hidden border border-slate-800 bg-slate-900/60 p-2 shadow-lg">
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800/80 mb-2">
        <div className="flex items-center gap-2">
          <span className="font-bold text-amber-400 text-sm tracking-wider">XAU/USD</span>
          <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">M5</span>
          <span className="text-xs text-emerald-400 font-medium">ICT / SMC Live Multi-TF</span>
        </div>
        <div className="text-xs text-slate-400">
          Liquidity Sweeps & FVG Active
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
}
