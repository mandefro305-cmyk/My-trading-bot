import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from backend.app.config.settings import settings
from backend.app.database.session import SessionLocal
from backend.app.database.models import Trade
from backend.app.database.init_db import init_db
from backend.app.services.worker import worker
from backend.app.services.settings_service import SettingsService

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        init_db()
    except Exception as e:
        print(f"Warning: could not auto-initialize DB: {e}")
    await worker.start()

@app.on_event("shutdown")
async def shutdown():
    await worker.stop()

@app.get("/health")
def health():
    return {
        "status": "HEALTHY",
        "trading_mode": worker.trading_mode,
        "worker_running": worker.running
    }

@app.get("/api/v1/dashboard/overview")
def overview():
    risk_state = worker.risk_engine.get_state()
    active_client = worker.get_active_client()
    return {
        "trading_mode": worker.trading_mode,
        "account_id": active_client.account_id if active_client else "Not Configured",
        "symbol": settings.SYMBOL,
        "current_bid": worker.current_bid,
        "current_ask": worker.current_ask,
        "spread": round(worker.current_ask - worker.current_bid, 2),
        "balance": risk_state["daily_starting_equity"],
        "equity": round(risk_state["daily_starting_equity"] + risk_state["daily_pnl"], 2),
        "daily_pnl": risk_state["daily_pnl"],
        "daily_loss_pct": risk_state["daily_loss_pct"],
        "daily_trades": risk_state["daily_trade_count"],
        "max_daily_trades": risk_state["max_trades_per_day"],
        "consecutive_losses": risk_state["consecutive_losses"],
        "max_consecutive_losses": risk_state["max_consecutive_losses"],
        "manual_approval_required": risk_state["manual_approval_required"],
        "paused": risk_state["paused"],
        "can_trade": risk_state["can_trade"],
        "open_positions_count": len(worker.positions),
        "total_trades": 0,
        "win_rate": 0.0,
        "last_ai_analysis": worker.last_ai_analysis
    }

@app.get("/api/v1/positions")
def list_positions():
    return list(worker.positions.values())

@app.get("/api/v1/trades")
def list_trades():
    try:
        db = SessionLocal()
        trades = db.query(Trade).order_by(Trade.id.desc()).limit(50).all()
        res = [
            {
                "id": t.id,
                "trade_id": t.trade_id,
                "direction": t.direction,
                "volume": t.volume,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "profit": t.pnl,
                "pnl": t.pnl,
                "status": t.status,
                "created_at": t.opened_at.isoformat() if t.opened_at else None
            }
            for t in trades
        ]
        db.close()
        return res
    except Exception:
        return []

@app.get("/api/v1/candles")
async def get_candles(timeframe: str = "M5", count: int = 60):
    client = worker.get_active_client()
    if client:
        candles = await client.get_candles(symbol=settings.SYMBOL, timeframe=timeframe, count=count)
        if candles:
            return candles
    return [
        {"open": worker.current_bid - 0.5, "high": worker.current_bid + 1.0, "low": worker.current_bid - 1.0, "close": worker.current_bid, "volume": 100}
        for _ in range(count)
    ]

@app.get("/api/v1/news")
def get_news():
    return worker.news_engine.get_upcoming_events(limit=10)

class ControlReq(BaseModel):
    action: str
    mode: Optional[str] = None
    confirm_real: Optional[bool] = False

@app.post("/api/v1/controls")
def handle_controls(req: ControlReq):
    act = req.action.lower()
    if act == "pause":
        worker.risk_engine.paused = True
        SettingsService.set_setting("PAUSED", "true")
        return {"status": "PAUSED"}
    elif act == "resume":
        worker.risk_engine.paused = False
        SettingsService.set_setting("PAUSED", "false")
        return {"status": "RESUMED"}
    elif act == "closeall":
        worker.positions.clear()
        return {"status": "ALL_POSITIONS_CLOSED"}
    elif act == "set_mode" and req.mode:
        success = worker.set_trading_mode(req.mode.upper(), confirm_real=bool(req.confirm_real))
        return {"status": "MODE_CHANGED" if success else "MODE_CHANGE_REJECTED", "mode": worker.trading_mode}
    return {"status": "OK"}

@app.get("/")
def root():
    return {
        "service": "GoldHunter AI Trading Engine",
        "status": "RUNNING",
        "control_center": "Telegram Bot",
        "trading_mode": worker.trading_mode,
        "health": "/health"
    }
