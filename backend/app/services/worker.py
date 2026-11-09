import asyncio
import datetime
import uuid
import logging
from typing import Optional, Dict, Any, List
from backend.app.config.settings import settings
from backend.app.broker.exness.client import ExnessClient
from backend.app.strategy.ict_smc.strategy import MultiTimeframeStrategyEngine
from backend.app.risk.engine import RiskEngine
from backend.app.risk.partial_profit import PartialProfitEngine
from backend.app.news.engine import NewsEngine
from backend.app.ai.xkiro.client import XKiroClient
from backend.app.telegram.bot import TelegramControlBot
from backend.app.services.settings_service import SettingsService
from backend.app.database.session import SessionLocal
from backend.app.database.models import Trade, Position, AccountSnapshot

logger = logging.getLogger("worker")

class BackgroundWorker:
    """
    GoldHunter AI continuous trading worker for Exness Demo & Real.
    - Connects directly to Exness API (paper trading removed).
    - Multi-timeframe ICT/SMC analysis on live candles.
    - AI consensus confirmation with xKiro.
    - Deterministic risk & 3-stage partial profit-taking (TP1, TP2, TP3 + trailing).
    - Persistent database state and rich interactive Telegram control bot.
    """

    def __init__(self):
        self.running = False

        # Load persisted settings from DB or defaults
        stored = SettingsService.get_all_settings()
        self.trading_mode = stored["trading_mode"]  # "EXNESS_DEMO" or "EXNESS_REAL"
        self.live_confirmed = stored["live_confirmed"]

        self.risk_engine = RiskEngine(
            max_risk_pct=stored["max_risk_pct"],
            max_daily_loss_pct=stored["max_daily_loss_pct"],
            max_trades_per_day=stored["max_trades_per_day"],
            max_consecutive_losses=stored["max_consecutive_losses"]
        )
        self.risk_engine.paused = stored["paused"]

        self.pp_engine = PartialProfitEngine()
        self.strategy_engine = MultiTimeframeStrategyEngine()
        self.news_engine = NewsEngine()
        self.news_engine.blackout_before = stored["news_blackout_before"]
        self.news_engine.blackout_after = stored["news_blackout_after"]

        self.ai_client = XKiroClient()
        self.telegram_bot = TelegramControlBot(self.risk_engine, self)

        # Clients for Demo & Real accounts
        self.demo_client = self._init_exness_client("EXNESS_DEMO")
        self.real_client = self._init_exness_client("EXNESS_REAL")

        self.current_bid = 2900.0
        self.current_ask = 2900.25
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.last_ai_analysis = {
            "trading_bias": "Neutral",
            "confidence_score": 0.0,
            "reason": "Initializing market scanner..."
        }
        self._loop_task = None

    def _init_exness_client(self, mode: str) -> Optional[ExnessClient]:
        if mode == "EXNESS_DEMO":
            acc = settings.EXNESS_DEMO_ACCOUNT_ID or settings.EXNESS_ACCOUNT_ID
            key = settings.EXNESS_DEMO_API_KEY or settings.EXNESS_API_KEY
            priv = settings.EXNESS_DEMO_PRIVATE_KEY_B64 or settings.EXNESS_PRIVATE_KEY_B64
        else:
            acc = settings.EXNESS_REAL_ACCOUNT_ID or settings.EXNESS_ACCOUNT_ID
            key = settings.EXNESS_REAL_API_KEY or settings.EXNESS_API_KEY
            priv = settings.EXNESS_REAL_PRIVATE_KEY_B64 or settings.EXNESS_PRIVATE_KEY_B64

        return ExnessClient(
            base_url=settings.EXNESS_API_BASE_URL,
            account_id=acc or "",
            api_key=key or "",
            private_key_b64=priv
        )

    def get_active_client(self) -> Optional[ExnessClient]:
        if self.trading_mode == "EXNESS_REAL":
            return self.real_client or self.demo_client
        return self.demo_client

    def set_trading_mode(self, new_mode: str, confirm_real: bool = False) -> bool:
        if new_mode == "EXNESS_REAL" and not confirm_real:
            return False
        self.trading_mode = new_mode
        if new_mode == "EXNESS_REAL":
            self.live_confirmed = True
        SettingsService.set_setting("TRADING_MODE", new_mode)
        SettingsService.set_setting("LIVE_TRADING_CONFIRMED", "true" if self.live_confirmed else "false")
        return True

    async def start(self):
        self.running = True
        self.news_engine.populate_seed_events_if_empty()
        # Start WebSocket streaming for real-time Exness ticks
        client = self.get_active_client()
        if client:
            client.start_websocket_stream(settings.SYMBOL)
        await self.telegram_bot.start_polling()
        self._loop_task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        client = self.get_active_client()
        if client:
            client.stop_websocket_stream()
        if self._loop_task:
            self._loop_task.cancel()
        await self.telegram_bot.stop()

    async def _main_loop(self):
        last_briefing_hour = -1
        while self.running:
            try:
                await self._sync_account_and_market()
                await self._manage_positions()
                await self._scan_market()

                # Check price alerts and upcoming news warnings on every cycle
                await self.telegram_bot.check_price_alerts(self.current_bid)
                await self.telegram_bot.check_upcoming_news_warning()

                # Session briefings at London Open (07:00 UTC) and NY Open (13:00 UTC)
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                if now_utc.hour in [7, 13] and now_utc.hour != last_briefing_hour:
                    session_name = "London Open 🇬🇧" if now_utc.hour == 7 else "New York Open 🇺🇸"
                    await self.telegram_bot.send_session_briefing(session_name)
                    last_briefing_hour = now_utc.hour

                # Throttled to 15 seconds to stay comfortably within Exness and Cloudflare rate limits
                await asyncio.sleep(15.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker main loop iteration error: {e}")
                await asyncio.sleep(15.0)

    async def _sync_account_and_market(self):
        client = self.get_active_client()
        if client:
            # 1. Update quote (never let quote failure block account sync or position checks)
            try:
                quote = await client.get_quote(settings.SYMBOL)
                self.current_bid = quote.get("bid", self.current_bid)
                self.current_ask = quote.get("ask", self.current_ask)
            except Exception as e:
                logger.debug(f"Market quote sync note: {e}")

            # 2. Update account summary & balance
            try:
                summary = await client.get_account_summary()
                if summary.get("is_live_synced"):
                    bal = float(summary.get("balance", self.risk_engine.daily_starting_equity))
                    self.risk_engine.daily_starting_equity = bal
            except Exception as e:
                logger.debug(f"Account summary sync note: {e}")

            # 3. Sync open positions from Exness
            try:
                ex_positions = await client.get_open_positions()
                if ex_positions:
                    for p in ex_positions:
                        pid = str(p.get("id"))
                        if pid not in self.positions:
                            self.positions[pid] = {
                                "id": pid,
                                "symbol": p.get("instrument", settings.SYMBOL),
                                "direction": p.get("side", "buy").lower(),
                                "volume": float(p.get("volume", 0.01)),
                                "original_volume": float(p.get("volume", 0.01)),
                                "open_price": float(p.get("open_price", self.current_bid)),
                                "stop_loss": float(p.get("stop_loss", 0.0)),
                                "take_profit_1": float(p.get("take_profit", 0.0)),
                                "take_profit_2": float(p.get("take_profit", 0.0)),
                                "take_profit_3": 0.0,
                                "tp1_hit": False,
                                "tp2_hit": False
                            }
            except Exception as e:
                logger.debug(f"Exness open positions sync note: {e}")

    async def _manage_positions(self):
        client = self.get_active_client()
        for pos_id, pos in list(self.positions.items()):
            actions = self.pp_engine.check_position(pos, self.current_bid, self.current_ask)
            for act in actions:
                if act["action"] == "CLOSE_PARTIAL":
                    vol = act["volume"]
                    stage = act["stage"]
                    if client:
                        try:
                            await client.close_position(pos_id, volume=str(vol))
                        except Exception as e:
                            logger.error(f"Exness partial close error: {e}")

                    pos["volume"] = max(0.0, round(pos["volume"] - vol, 2))
                    if stage == "TP1":
                        pos["tp1_hit"] = True
                        if act.get("move_sl_to_be"):
                            pos["stop_loss"] = pos["open_price"]
                            if client:
                                try:
                                    await client.update_position_sl_tp(pos_id, stop_loss_price=pos["open_price"])
                                except Exception as e:
                                    logger.error(f"Failed to move SL to BE on Exness: {e}")
                    elif stage == "TP2":
                        pos["tp2_hit"] = True

                    await self.telegram_bot.send_notification(
                        f"🎯 <b>Partial Take Profit Hit ({stage})!</b>\n"
                        f"Position #{pos_id} closed {vol} lots @ {act['exec_price']:.2f}\n"
                        f"Remaining: {pos['volume']} lots"
                    )

                elif act["action"] == "CLOSE_FULL":
                    if client:
                        try:
                            await client.close_position(pos_id)
                        except Exception as e:
                            logger.error(f"Exness full close error: {e}")

                    self.positions.pop(pos_id, None)
                    pnl = (act["exec_price"] - pos["open_price"]) * pos["volume"] * 100.0 if pos["direction"] == "buy" else (pos["open_price"] - act["exec_price"]) * pos["volume"] * 100.0
                    self.risk_engine.record_trade_result(pnl)

                    # Persist trade in DB
                    try:
                        db = SessionLocal()
                        t = Trade(
                            trade_id=str(pos.get("trade_id") or f"TR-{uuid.uuid4().hex[:8]}"),
                            account_id=str(client.account_id if client else "exness-account"),
                            mode=self.trading_mode,
                            symbol=settings.SYMBOL,
                            direction=pos["direction"].upper(),
                            volume=pos["original_volume"],
                            entry_price=pos["open_price"],
                            exit_price=act["exec_price"],
                            stop_loss=pos.get("stop_loss", 0.0),
                            take_profit_1=pos.get("take_profit_1", 0.0),
                            take_profit_2=pos.get("take_profit_2", 0.0),
                            take_profit_3=pos.get("take_profit_3", 0.0),
                            pnl=pnl,
                            status="CLOSED",
                            close_reason=act.get("reason", "CLOSED"),
                            closed_at=datetime.datetime.now(datetime.timezone.utc)
                        )
                        db.add(t)
                        db.commit()
                        db.close()
                    except Exception as db_err:
                        logger.error(f"Failed to save closed trade in DB: {db_err}")

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

        client = self.get_active_client()
        if not client or not client.account_id:
            return

        # Fetch separate timeframes for true ICT/SMC multi-timeframe analysis
        m5_candles = await client.get_candles(settings.SYMBOL, timeframe="M5", count=40)
        if not m5_candles or len(m5_candles) < 20:
            logger.debug("M5 market candles insufficient or unavailable from broker; skipping scan.")
            return

        m15_candles = await client.get_candles(settings.SYMBOL, timeframe="M15", count=30)
        h1_candles = await client.get_candles(settings.SYMBOL, timeframe="H1", count=30)
        h4_candles = await client.get_candles(settings.SYMBOL, timeframe="H4", count=30)

        if len(m15_candles) < 20 or len(h1_candles) < 20 or len(h4_candles) < 20:
            return

        setup = self.strategy_engine.analyze(
            h4_candles=h4_candles,
            h1_candles=h1_candles,
            m15_candles=m15_candles,
            m5_candles=m5_candles,
            current_bid=self.current_bid,
            current_ask=self.current_ask
        )
        if not setup:
            return

        size_ok, lots, _ = self.risk_engine.calculate_position_size(
            equity=state["daily_starting_equity"] + state["daily_pnl"],
            entry_price=setup["entry_price"],
            stop_loss=setup["stop_loss"]
        )
        if not size_ok or lots < 0.01:
            return

        ai_res = await self.ai_client.analyze_market(
            symbol=settings.SYMBOL,
            current_price=setup["entry_price"],
            technical_summary={"direction": setup["direction"]}
        )
        self.last_ai_analysis = ai_res.model_dump()

        # In strict broker execution mode, send order to Exness and confirm execution
        pos_id = None
        if client:
            try:
                res = await client.open_position(
                    symbol=settings.SYMBOL,
                    side=setup["direction"],
                    volume=str(lots),
                    stop_loss_price=str(setup["stop_loss"]),
                    take_profit_price=str(setup["tp2"])
                )
                if res and ("position" in res or "operation" in res or "ack" in res):
                    # Check operation confirmation or returned position object
                    pos_obj = res.get("position", {})
                    op_obj = res.get("operation", {})
                    if op_obj and op_obj.get("status") in ["rejected", "failed"]:
                        logger.error(f"Exness order execution rejected/failed: {op_obj}")
                        return
                    pos_id = str(pos_obj.get("id") or op_obj.get("position_id") or res.get("ack", {}).get("position_id") or "")
            except Exception as e:
                logger.error(f"Exness order execution failed: {e}")
                return

        # Do not record phantom trades if order was rejected or could not be verified
        if not pos_id:
            logger.warning("Order execution could not be verified with broker. Aborting position registration.")
            return

        new_pos = {
            "id": pos_id,
            "symbol": settings.SYMBOL,
            "direction": setup["direction"].lower(),
            "volume": lots,
            "original_volume": lots,
            "open_price": setup["entry_price"],
            "stop_loss": setup["stop_loss"],
            "take_profit_1": setup["tp1"],
            "take_profit_2": setup["tp2"],
            "take_profit_3": setup["tp3"],
            "tp1_hit": False,
            "tp2_hit": False
        }
        self.positions[pos_id] = new_pos

        # Save to DB
        try:
            db = SessionLocal()
            pos_db = Position(
                position_id=pos_id,
                account_id=str(client.account_id if client else "exness-account"),
                mode=self.trading_mode,
                symbol=settings.SYMBOL,
                direction=setup["direction"].upper(),
                initial_volume=lots,
                current_volume=lots,
                open_price=setup["entry_price"],
                current_price=setup["entry_price"],
                stop_loss=setup["stop_loss"],
                take_profit=setup["tp2"],
                state="OPEN"
            )
            db.add(pos_db)
            db.commit()
            db.close()
        except Exception as db_err:
            logger.error(f"Failed to persist position in DB: {db_err}")

        # Send interactive Telegram alert
        await self.telegram_bot.send_trade_alert(new_pos, ai_res)

    async def open_manual_trade(
        self,
        side: str,
        volume: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        is_pending: bool = False,
        pending_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes a manual market or pending trade with deterministic risk sizing and 3-stage profit management.
        """
        client = self.get_active_client()
        side = side.lower()
        if side not in ["buy", "sell"]:
            return {"success": False, "error": "Invalid order side. Must be BUY or SELL."}

        # Check risk limits
        st = self.risk_engine.get_state()
        if not st["can_trade"]:
            return {"success": False, "error": f"Trading restricted by risk engine. Daily loss: {st['daily_loss_pct']:.2f}%"}

        current_entry = self.current_ask if side == "buy" else self.current_bid
        if is_pending and pending_price:
            entry_price = float(pending_price)
        else:
            entry_price = current_entry

        # ATR / default SL and TP if not specified
        default_sl_dist = 4.0  # $4.00 default gold SL distance if ATR unavailable
        try:
            m5 = await client.get_candles(settings.SYMBOL, timeframe="M5", count=20) if client else []
            if m5 and len(m5) >= 14:
                from backend.app.strategy.ict_smc.indicators import calculate_atr
                atr_val = calculate_atr(m5, period=14)
                if atr_val > 0.5:
                    default_sl_dist = round(atr_val * 1.5, 2)
        except Exception:
            pass

        if stop_loss is None or stop_loss <= 0:
            stop_loss = round(entry_price - default_sl_dist if side == "buy" else entry_price + default_sl_dist, 2)

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0.1:
            return {"success": False, "error": "Stop loss is too close to entry price."}

        # Calculate lot size
        if volume is not None and volume >= 0.01:
            lots = round(float(volume), 2)
        else:
            size_ok, calculated_lots, _ = self.risk_engine.calculate_position_size(
                equity=st["daily_starting_equity"] + st["daily_pnl"],
                entry_price=entry_price,
                stop_loss=stop_loss
            )
            lots = calculated_lots if size_ok and calculated_lots >= 0.01 else 0.01

        # 3-Stage TP Engine: TP1 = 1R (40%), TP2 = 2R (30%), TP3 = 3R (30%)
        if side == "buy":
            tp1 = round(entry_price + sl_distance, 2)
            tp2 = round(entry_price + 2.0 * sl_distance, 2) if not take_profit else float(take_profit)
            tp3 = round(entry_price + 3.0 * sl_distance, 2)
        else:
            tp1 = round(entry_price - sl_distance, 2)
            tp2 = round(entry_price - 2.0 * sl_distance, 2) if not take_profit else float(take_profit)
            tp3 = round(entry_price - 3.0 * sl_distance, 2)

        # Transmit order to Exness
        pos_id = None
        if client:
            try:
                res = await client.open_position(
                    symbol=settings.SYMBOL,
                    side=side,
                    volume=str(lots),
                    stop_loss_price=str(stop_loss),
                    take_profit_price=str(tp2)
                )
                if res and ("position" in res or "operation" in res or "ack" in res):
                    pos_obj = res.get("position", {})
                    op_obj = res.get("operation", {})
                    if op_obj and op_obj.get("status") in ["rejected", "failed"]:
                        return {"success": False, "error": f"Broker rejected order: {op_obj.get('error_message', 'Rejected')}"}
                    pos_id = str(pos_obj.get("id") or op_obj.get("position_id") or res.get("ack", {}).get("position_id") or "")
            except Exception as e:
                logger.error(f"Manual order dispatch error: {e}")
                return {"success": False, "error": f"Broker API execution error: {str(e)}"}

        if not pos_id:
            return {"success": False, "error": "Order could not be confirmed by broker."}

        new_pos = {
            "id": pos_id,
            "symbol": settings.SYMBOL,
            "direction": side,
            "volume": lots,
            "original_volume": lots,
            "open_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "tp1_hit": False,
            "tp2_hit": False,
            "is_manual": True
        }
        self.positions[pos_id] = new_pos

        # Persist position in database
        try:
            db = SessionLocal()
            pos_db = Position(
                position_id=pos_id,
                account_id=str(client.account_id if client else "exness-account"),
                mode=self.trading_mode,
                symbol=settings.SYMBOL,
                direction=side.upper(),
                initial_volume=lots,
                current_volume=lots,
                open_price=entry_price,
                current_price=entry_price,
                stop_loss=stop_loss,
                take_profit=tp2,
                state="OPEN"
            )
            db.add(pos_db)
            db.commit()
            db.close()
        except Exception as db_err:
            logger.error(f"Failed to persist manual position in DB: {db_err}")

        # Send Telegram notification
        await self.telegram_bot.send_notification(
            f"🎯 <b>Manual {side.upper()} Order Executed!</b>\n\n"
            f"• Position ID: <code>#{pos_id}</code>\n"
            f"• Volume: <b>{lots} lots</b>\n"
            f"• Entry: <b>${entry_price:.2f}</b>\n"
            f"• SL: <b>${stop_loss:.2f}</b>\n"
            f"• TP1 (40% + BE): <b>${tp1:.2f}</b>\n"
            f"• TP2 (30%): <b>${tp2:.2f}</b>\n"
            f"• TP3 (30%): <b>${tp3:.2f}</b>"
        )
        return {"success": True, "position": new_pos}

worker = BackgroundWorker()
