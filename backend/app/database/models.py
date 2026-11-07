import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from backend.app.database.session import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="owner")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(64), unique=True, index=True, nullable=False)
    account_type = Column(String(20), default="PAPER")
    currency = Column(String(10), default="USD")
    leverage = Column(String(20), default="100")
    balance = Column(Float, default=10000.0)
    equity = Column(Float, default=10000.0)
    used_margin = Column(Float, default=0.0)
    free_margin = Column(Float, default=10000.0)
    trade_mode = Column(String(20), default="enabled")
    account_status = Column(String(20), default="active")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False)
    description = Column(String(100), default="Gold vs US Dollar")
    point_digits = Column(Integer, default=2)
    contract_size = Column(Float, default=100.0)
    volume_min = Column(Float, default=0.01)
    volume_max = Column(Float, default=100.0)
    volume_step = Column(Float, default=0.01)
    spread = Column(Float, default=0.25)
    commission = Column(Float, default=0.0)
    trade_mode = Column(String(20), default="enabled")

class MarketPrice(Base):
    __tablename__ = "market_prices"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class Candle(Base):
    __tablename__ = "candles"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    open_time = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)

class TradingSignal(Base):
    __tablename__ = "trading_signals"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), default="XAUUSD")
    direction = Column(String(10), nullable=False)
    timeframe = Column(String(10), default="M5")
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)
    take_profit_3 = Column(Float, nullable=False)
    risk_reward = Column(Float, default=2.0)
    liquidity_sweep_type = Column(String(50))
    displacement_confirmed = Column(Boolean, default=False)
    fvg_zone = Column(String(100))
    status = Column(String(20), default="PENDING")
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(64), unique=True, index=True, nullable=False)
    account_id = Column(String(64), index=True, nullable=False)
    mode = Column(String(20), default="PAPER")
    symbol = Column(String(20), default="XAUUSD")
    direction = Column(String(10), nullable=False)
    volume = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)
    take_profit_3 = Column(Float, nullable=False)
    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    swap = Column(Float, default=0.0)
    status = Column(String(20), default="OPEN")
    close_reason = Column(String(50), nullable=True)
    opened_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    closed_at = Column(DateTime, nullable=True)

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(String(64), unique=True, index=True, nullable=False)
    trade_id = Column(String(64), ForeignKey("trades.trade_id"), nullable=True)
    account_id = Column(String(64), index=True, nullable=False)
    mode = Column(String(20), default="PAPER")
    symbol = Column(String(20), default="XAUUSD")
    direction = Column(String(10), nullable=False)
    initial_volume = Column(Float, nullable=False)
    current_volume = Column(Float, nullable=False)
    open_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    state = Column(String(20), default="OPEN")
    opened_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PartialProfitEvent(Base):
    __tablename__ = "partial_profit_events"
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(String(64), index=True, nullable=False)
    stage = Column(String(10), nullable=False)
    closed_volume = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    sl_moved_to_be = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), default="XAUUSD")
    market_direction = Column(String(20))
    trading_bias = Column(String(20))
    confidence_score = Column(Float)
    supporting_evidence = Column(JSON)
    contradictory_evidence = Column(JSON)
    important_liquidity_levels = Column(JSON)
    entry_zone = Column(String(100))
    sl_suggestion = Column(Float)
    tp_suggestions = Column(JSON)
    risk_warnings = Column(JSON)
    news_impact = Column(String(100))
    reason = Column(Text)
    raw_response = Column(JSON)
    model_used = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class NewsEvent(Base):
    __tablename__ = "news_events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    source = Column(String(100))
    impact = Column(String(20), default="LOW")
    summary = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class EconomicCalendar(Base):
    __tablename__ = "economic_calendar"
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(200), nullable=False)
    currency = Column(String(10), default="USD")
    impact = Column(String(20), default="HIGH")
    event_time = Column(DateTime, index=True, nullable=False)
    actual = Column(String(50), nullable=True)
    forecast = Column(String(50), nullable=True)
    previous = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    daily_pnl = Column(Float)
    consecutive_losses = Column(Integer)
    action_taken = Column(String(100))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class ManualApproval(Base):
    __tablename__ = "manual_approvals"
    id = Column(Integer, primary_key=True, index=True)
    reason = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    status = Column(String(20), default="PENDING")
    requested_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(50), nullable=True)

class DailyPerformance(Base):
    __tablename__ = "daily_performance"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), unique=True, index=True, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    profit_loss = Column(Float, default=0.0)
    profit_loss_pct = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    ending_equity = Column(Float, default=10000.0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(64), index=True, nullable=False)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    used_margin = Column(Float, default=0.0)
    open_positions_count = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ApiUsage(Base):
    __tablename__ = "api_usage"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), index=True, nullable=False)
    endpoint = Column(String(255), nullable=False)
    tokens_used = Column(Integer, default=0)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), default="INFO", index=True)
    component = Column(String(50), index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(String(64), index=True, nullable=True)
    client_request_id = Column(String(128), index=True, nullable=True)
    event_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    error_code = Column(Integer, nullable=True)
    error_message = Column(String(255), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
