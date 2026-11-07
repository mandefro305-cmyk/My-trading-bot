from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import datetime
from pydantic import BaseModel
from backend.app.config.settings import settings
from backend.app.database.session import SessionLocal
from backend.app.database.models import Position, Trade
from backend.app.services.worker import worker

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
    await worker.start()

@app.on_event("shutdown")
async def shutdown():
    await worker.stop()

@app.get("/health")
def health():
    return {
        "status": "HEALTHY",
        "trading_mode": settings.TRADING_MODE,
        "worker_running": worker.running
    }

@app.get("/api/v1/dashboard/overview")
def overview():
    risk_state = worker.risk_engine.get_state()
    return {
        "trading_mode": settings.TRADING_MODE,
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
        "open_positions_count": len(worker.mock_gateway.positions),
        "total_trades": 0,
        "win_rate": 0.0,
        "last_ai_analysis": worker.last_ai_analysis
    }

@app.get("/api/v1/positions")
def list_positions():
    return list(worker.mock_gateway.positions.values())

@app.get("/api/v1/trades")
def list_trades():
    return []

@app.get("/api/v1/candles")
async def get_candles(timeframe: str = "M5", count: int = 60):
    return await worker.mock_gateway.get_candles(symbol="XAUUSD", timeframe=timeframe, count=count)

@app.get("/api/v1/news")
def get_news():
    return worker.news_engine.get_upcoming_events(limit=10)

class ControlReq(BaseModel):
    action: str

@app.post("/api/v1/controls")
def handle_controls(req: ControlReq):
    act = req.action.lower()
    if act == "pause":
        worker.risk_engine.paused = True
        return {"status": "PAUSED"}
    elif act == "resume":
        worker.risk_engine.paused = False
        return {"status": "RESUMED"}
    elif act == "closeall":
        worker.mock_gateway.positions.clear()
        return {"status": "ALL_POSITIONS_CLOSED"}
    return {"status": "OK"}
