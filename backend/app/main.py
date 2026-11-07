import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import datetime
from pydantic import BaseModel
from backend.app.config.settings import settings
from backend.app.database.session import SessionLocal
from backend.app.database.models import Position, Trade
from backend.app.database.init_db import init_db
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
    try:
        db = SessionLocal()
        trades = db.query(Trade).order_by(Trade.id.desc()).limit(50).all()
        res = [
            {
                "id": t.id,
                "direction": t.direction,
                "volume": t.volume,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "profit": t.profit,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in trades
        ]
        db.close()
        return res
    except Exception:
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

# Serve frontend build if dist folder exists
frontend_dist = os.path.join(os.getcwd(), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
