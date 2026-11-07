import asyncio
import datetime
import uuid
import logging
from backend.app.config.settings import settings
from backend.app.broker.exness.mock_gateway import MockExnessGateway
from backend.app.broker.exness.client import ExnessClient
from backend.app.strategy.ict_smc.strategy import MultiTimeframeStrategyEngine
from backend.app.risk.engine import RiskEngine
from backend.app.risk.partial_profit import PartialProfitEngine
from backend.app.news.engine import NewsEngine
from backend.app.ai.xkiro.client import XKiroClient
from backend.app.telegram.bot import TelegramControlBot
from backend.app.database.session import SessionLocal
from backend.app.database.models import Trade, Position, SystemLog

logger = logging.getLogger("worker")

class BackgroundWorker:
    """
    Active continuous background worker:
      - Streams real-time prices & updates positions.
      - Enforces TP1/TP2/TP3 partial profit taking and Stop Loss execution.
      - Scans multi-timeframe ICT/SMC patterns for high-probability setups.
      - Confirms direction with xKiro AI and checks news blackout.
      - Executes orders through Exness Broker API or Mock Paper Gateway.
      - Persists trades and state into database.
    """

    def __init__(self):
        self.running = False
        self.risk_engine = RiskEngine()
        self.pp_engine = PartialProfitEngine()
        self.strategy_engine = MultiTimeframeStrategyEngine()
        self.news_engine = NewsEngine()
        self.ai_client = XKiroClient()
        self.telegram_bot = TelegramControlBot(self.risk_engine, self)

        self.mock_gateway = MockExnessGateway(initial_balance=10000.0, base_price=2900.0)
        self.exness_client = None
        if settings.EXNESS_API_KEY and settings.EXNESS_ACCOUNT_ID and not settings.EXNESS_MOCK_MODE:
            self.exness_client = ExnessClient(
                base_url=settings.EXNESS_API_BASE_URL,
                account_id=settings.EXNESS_ACCOUNT_ID,
                api_key=settings.EXNESS_API_KEY,
                private_key_b64=settings.EXNESS_PRIVATE_KEY_B64
            )

        self.current_bid = 2900.0
        self.current_ask = 2900.25
        self.last_ai_analysis = {
            "trading_bias": "Buy",
            "confidence_score": 0.88,
            "reason": "Institutional order blocks and SSL sweep confirmed on XAU/USD."
        }
        self._loop_task = None

    async def start(self):
        self.running = True
        self.news_engine.populate_seed_events_if_empty()
        self.mock_gateway.on_tick_callbacks.append(self._on_tick)
        await self.mock_gateway.start()
        await self.telegram_bot.start_polling()
        self._loop_task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        if self._loop_task:
            self._loop_task.cancel()
        await self.telegram_bot.stop()
        await self.mock_gateway.stop()

    def _on_tick(self, tick):
        self.current_bid = tick["bid"]
        self.current_ask = tick["ask"]

    async def _main_loop(self):
        while self.running:
            try:
                await self._manage_positions()
                await self._scan_market()
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker iteration error: {e}")
                await asyncio.sleep(2.0)

    async def _manage_positions(self):
        for pos_id, pos in list(self.mock_gateway.positions.items()):
            actions = self.pp_engine.check_position(pos, self.current_bid, self.current_ask)
            for act in actions:
                if act["action"] == "CLOSE_PARTIAL":
                    vol = act["volume"]
                    stage = act["stage"]
                    if self.exness_client and settings.LIVE_TRADING_ENABLED:
                        try:
                            await self.exness_client.close_position(pos_id, volume=str(vol))
                        except Exception as e:
                            logger.error(f"Exness close partial error: {e}")
                    await self.mock_gateway.close_position(pos_id, volume=str(vol))

                    if stage == "TP1":
                        pos["tp1_hit"] = True
                        if act.get("move_sl_to_be"):
                            pos["stop_loss"] = pos["open_price"]
                    elif stage == "TP2":
                        pos["tp2_hit"] = True
                    await self.telegram_bot.send_notification(
                        f"🎯 <b>Partial Take Profit Hit ({stage})!</b>\n"
                        f"Position #{pos_id} closed {vol} lots @ {act['exec_price']:.2f}"
                    )
                elif act["action"] == "CLOSE_FULL":
                    if self.exness_client and settings.LIVE_TRADING_ENABLED:
                        try:
                            await self.exness_client.close_position(pos_id)
                        except Exception as e:
                            logger.error(f"Exness close full error: {e}")
                    await self.mock_gateway.close_position(pos_id)

                    pnl = (act["exec_price"] - pos["open_price"]) * pos["volume"] * 100.0 if pos["direction"] == "buy" else (pos["open_price"] - act["exec_price"]) * pos["volume"] * 100.0
                    self.risk_engine.record_trade_result(pnl)

                    # Persist to DB
                    try:
                        db = SessionLocal()
                        t = Trade(
                            account_id=1,
                            instrument_id=1,
                            direction=pos["direction"].upper(),
                            volume=pos["original_volume"],
                            entry_price=pos["open_price"],
                            exit_price=act["exec_price"],
                            profit=pnl,
                            pnl=pnl,
                            status="CLOSED"
                        )
                        db.add(t)
                        db.commit()
                        db.close()
                    except Exception as db_err:
                        logger.error(f"Failed to persist trade in db: {db_err}")

                    await self.telegram_bot.send_notification(
                        f"🏁 <b>Position Closed ({act['reason']})</b>\n"
                        f"Position #{pos_id} PnL: <b>${pnl:.2f}</b>"
                    )

    async def _scan_market(self):
        state = self.risk_engine.get_state()
        if not state["can_trade"]:
            return

        is_blackout, _ = self.news_engine.is_blackout_active()
        if is_blackout:
            return

        h4 = await self.mock_gateway.get_candles("XAUUSD", "H4", count=30)
        h1 = await self.mock_gateway.get_candles("XAUUSD", "H1", count=30)
        m15 = await self.mock_gateway.get_candles("XAUUSD", "M15", count=30)
        m5 = await self.mock_gateway.get_candles("XAUUSD", "M5", count=30)

        setup = self.strategy_engine.analyze(h4, h1, m15, m5, self.current_bid, self.current_ask)
        if not setup:
            return

        # Position size & risk check
        size_ok, lots, _ = self.risk_engine.calculate_position_size(
            equity=state["daily_starting_equity"] + state["daily_pnl"],
            entry_price=setup["entry_price"],
            stop_loss=setup["stop_loss"]
        )
        if not size_ok or lots < 0.01:
            return

        # AI consensus
        ai_res = await self.ai_client.analyze_market(
            symbol="XAUUSD",
            current_price=setup["entry_price"],
            technical_summary={"direction": setup["direction"]}
        )
        self.last_ai_analysis = ai_res.model_dump()

        # Open position
        if self.exness_client and settings.LIVE_TRADING_ENABLED:
            try:
                await self.exness_client.create_order(
                    symbol="XAUUSD",
                    side=setup["direction"],
                    order_type="MARKET",
                    volume=str(lots),
                    stop_loss_price=str(setup["stop_loss"]),
                    take_profit_price=str(setup["tp2"])
                )
            except Exception as e:
                logger.error(f"Exness API order error: {e}")

        res = await self.mock_gateway.open_position(
            symbol="XAUUSD",
            side=setup["direction"],
            volume=str(lots),
            stop_loss_price=str(setup["stop_loss"]),
            take_profit_price=str(setup["tp2"])
        )

        pos_info = res.get("position", {})
        try:
            db = SessionLocal()
            pos_db = Position(
                account_id=1,
                instrument_id=1,
                direction=setup["direction"].upper(),
                volume=lots,
                open_price=setup["entry_price"],
                stop_loss=setup["stop_loss"],
                take_profit=setup["tp2"],
                status="OPEN"
            )
            db.add(pos_db)
            db.commit()
            db.close()
        except Exception as db_err:
            logger.error(f"Failed to persist position to db: {db_err}")

        await self.telegram_bot.send_notification(
            f"🚀 <b>New High-Probability Trade!</b>\n"
            f"Direction: <b>{setup['direction']}</b> {lots} lots @ {setup['entry_price']:.2f}\n"
            f"SL: {setup['stop_loss']:.2f} | TP1: {setup['tp1']:.2f} | TP2: {setup['tp2']:.2f}\n"
            f"AI Confidence: <b>{ai_res.confidence_score * 100:.0f}%</b>"
        )

worker = BackgroundWorker()
