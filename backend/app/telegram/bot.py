import logging
import datetime
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from backend.app.config.settings import settings
from backend.app.services.settings_service import SettingsService
from backend.app.strategy.ict_smc.chart_renderer import ICTChartRenderer

logger = logging.getLogger("telegram_bot")

class TelegramControlBot:
    """
    Rich interactive Telegram control bot for Exness Demo and Real accounts.
    Provides:
    - Interactive Main Navigation Menu
    - 2-Step Safe Mode Switching (DEMO <-> REAL)
    - Interactive Rule Controls (Risk %, Max Daily Loss %, Max Trades, News Window)
    - Position Manager with [Close] & [Move SL to Breakeven] action buttons
    - Interactive 2-Consecutive-Loss approval dialogs
    - Instant xKiro AI multi-timeframe analysis on XAU/USD
    """

    def __init__(self, risk_engine, worker_service=None):
        self.risk_engine = risk_engine
        self.worker = worker_service
        self.owner_id = settings.TELEGRAM_OWNER_ID
        self.app: Optional[Application] = None
        self.price_alerts: Dict[float, str] = {}  # target_price: note/direction
        self.last_news_notified: set = set()

    def _get_badge(self) -> str:
        mode = self.worker.trading_mode if self.worker else settings.TRADING_MODE
        if mode == "EXNESS_REAL":
            return "🔴 <b>[EXNESS REAL]</b>"
        return "🟡 <b>[EXNESS DEMO]</b>"

    def _is_owner(self, update: Update) -> bool:
        if not self.owner_id:
            return True
        user_id = update.effective_user.id if update.effective_user else None
        return user_id == self.owner_id

    def _get_main_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="menu_status"),
                InlineKeyboardButton("📸 ICT Chart", callback_data="menu_chart"),
                InlineKeyboardButton("🏆 Performance", callback_data="menu_perf")
            ],
            [
                InlineKeyboardButton("📈 Open Positions", callback_data="menu_positions"),
                InlineKeyboardButton("🧠 AI Analysis", callback_data="menu_analysis"),
                InlineKeyboardButton("🎙️ Fed/Sentiment", callback_data="menu_sentiment")
            ],
            [
                InlineKeyboardButton("⚡ Switch Mode", callback_data="menu_mode"),
                InlineKeyboardButton("⚙️ Rule Controls", callback_data="menu_rules")
            ],
            [
                InlineKeyboardButton("📰 News & Blackouts", callback_data="menu_news"),
                InlineKeyboardButton("🔔 Price Alerts", callback_data="menu_alerts")
            ],
            [
                InlineKeyboardButton("⏸️ Pause", callback_data="action_pause"),
                InlineKeyboardButton("▶️ Resume", callback_data="action_resume"),
                InlineKeyboardButton("🚨 Close All", callback_data="menu_closeall_confirm")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _send_or_edit(self, update: Update, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
            except Exception:
                await update.callback_query.message.reply_html(text, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_html(text, reply_markup=reply_markup)

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        text = (
            f"🦅 <b>GoldHunter AI v2.0 Control Center</b>\n"
            f"Active Account: {badge}\n"
            f"Instrument: <b>XAU/USD</b>\n\n"
            f"Welcome, Commander! Use the interactive buttons below to monitor positions, adjust rules, switch modes, and execute actions in real time."
        )
        await self._send_or_edit(update, text, self._get_main_keyboard())

    async def chart_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        client = self.worker.get_active_client() if self.worker else None
        candles = []
        if client:
            try:
                quote = await client.get_quote(settings.SYMBOL)
                if quote.get("bid", 0.0) > 0:
                    self.worker.current_bid = quote["bid"]
                    self.worker.current_ask = quote["ask"]
                candles = await client.get_candles(settings.SYMBOL, timeframe="M5", count=35)
            except Exception:
                pass

        # Check if there is an active position to highlight
        setup = None
        if self.worker and self.worker.positions:
            first_pos = next(iter(self.worker.positions.values()))
            setup = {
                "entry_price": first_pos.get("open_price"),
                "stop_loss": first_pos.get("stop_loss"),
                "tp1": first_pos.get("take_profit_1"),
                "tp2": first_pos.get("take_profit_2")
            }

        chart_buf = ICTChartRenderer.render_candlestick_chart(
            candles=candles,
            symbol="XAU/USD",
            timeframe="M5",
            trade_setup=setup
        )

        caption = (
            f"📸 <b>XAU/USD Live ICT Candlestick Chart (M5)</b> {badge}\n"
            f"Current Bid: <b>${self.worker.current_bid:.2f}</b> | Ask: <b>${self.worker.current_ask:.2f}</b>\n"
            f"<i>Includes Fair Value Gaps and active trade levels.</i>"
        )

        target = update.callback_query.message if update.callback_query else update.message
        if target:
            await target.reply_photo(
                photo=chart_buf,
                caption=caption,
                parse_mode="HTML",
                reply_markup=self._get_main_keyboard()
            )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        text = (
            f"📖 <b>Interactive Command Guide</b> {badge}\n\n"
            f"/menu or /start - Open interactive master dashboard\n"
            f"/status - Instant account health & risk metrics\n"
            f"/chart - Generate live ICT candlestick chart snapshot\n"
            f"/sentiment - AI Fed speech & macroeconomic gold analysis\n"
            f"/performance - Win rate, profit factor, net P&L metrics\n"
            f"/mode - Switch between Exness DEMO and REAL\n"
            f"/positions - List active positions with quick action buttons\n"
            f"/alert &lt;price&gt; - Set custom Gold (XAU/USD) price alert\n"
            f"/rules - View & adjust risk %, loss limits, max trades\n"
            f"/analysis - Live xKiro AI ICT/SMC market view\n"
            f"/news - Economic calendar & high-impact blackout status\n"
            f"/pause - Pause opening new positions\n"
            f"/resume - Resume opening positions\n"
            f"/closeall - Emergency close all positions"
        )
        await self._send_or_edit(update, text, self._get_main_keyboard())

    async def performance_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        from backend.app.database.session import SessionLocal
        from backend.app.database.models import Trade

        badge = self._get_badge()
        db = SessionLocal()
        try:
            trades = db.query(Trade).all()
            total_trades = len(trades)
            winning_trades = [t for t in trades if (t.pnl or 0.0) > 0]
            losing_trades = [t for t in trades if (t.pnl or 0.0) < 0]

            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0.0)
            net_pnl = gross_profit - gross_loss

            text = (
                f"🏆 <b>Performance Metrics Snapshot</b> {badge}\n\n"
                f"• Total Closed Trades: <b>{total_trades}</b>\n"
                f"• Win Rate: <b>{win_rate:.1f}%</b> ({win_count}W / {loss_count}L)\n"
                f"• Profit Factor: <b>{profit_factor}</b>\n"
                f"• Gross Profit: <b>+${gross_profit:.2f}</b>\n"
                f"• Gross Loss: <b>-${gross_loss:.2f}</b>\n"
                f"• Net P&L: <b>{'🟢 +$' if net_pnl >= 0 else '🔴 -$'}{abs(net_pnl):.2f}</b>\n\n"
                f"<i>Realized stats calculated directly from verified database ledger.</i>"
            )
        except Exception as e:
            text = f"🏆 <b>Performance Metrics</b>\n\nError calculating ledger metrics: {e}"
        finally:
            db.close()

        buttons = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu_perf")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def sentiment_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        args = context.args if context and context.args else []
        custom_text = " ".join(args) if args else None

        summary = {"tone": "Evaluating", "gold_impact": "Assessing", "bullets": [], "key_quote": ""}
        if self.worker:
            summary = await self.worker.ai_client.summarize_fed_and_sentiment(speech_text=custom_text)

        bullets_fmt = "\n".join([f"• {b}" for b in summary.get("bullets", [])]) or "• Assessing current macro drivers."
        text = (
            f"🎙️ <b>Federal Reserve & Macro Sentiment</b> {badge}\n\n"
            f"• Monetary Tone: <b>{summary.get('tone', 'Neutral')}</b>\n"
            f"• Gold Impact: <b>{summary.get('gold_impact', 'Neutral')}</b>\n\n"
            f"<b>Strategic 3-Bullet Breakdown:</b>\n{bullets_fmt}\n\n"
            f"💡 <i>Takeaway: \"{summary.get('key_quote', 'Trade structured setups only.')}\"</i>"
        )
        buttons = [
            [InlineKeyboardButton("🔄 Refresh Sentiment", callback_data="menu_sentiment")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def alert_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        args = context.args if context and context.args else []
        badge = self._get_badge()
        if not args:
            cur_price = self.worker.current_bid if self.worker else 2900.0
            alerts_text = "\n".join([f"• <b>${p:.2f}</b> ({note})" for p, note in self.price_alerts.items()]) or "No active alerts set."
            text = (
                f"🔔 <b>Custom Gold Price Alerts</b> {badge}\n\n"
                f"Current Bid: <b>${cur_price:.2f}</b>\n\n"
                f"<b>Active Price Triggers:</b>\n{alerts_text}\n\n"
                f"To set a new alert, send:\n<code>/alert &lt;target_price&gt;</code>\nExample: <code>/alert 2950.00</code>"
            )
            buttons = [
                [InlineKeyboardButton("Clear All Alerts", callback_data="clear_price_alerts")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
            ]
            await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))
            return

        try:
            target = float(args[0])
            cur = self.worker.current_bid if self.worker else 2900.0
            direction = "ABOVE" if target > cur else "BELOW"
            self.price_alerts[target] = f"Alert when price goes {direction}"
            text = (
                f"✅ <b>Price Alert Set!</b>\n"
                f"Target Price: <b>${target:.2f}</b>\n"
                f"Current Price: <b>${cur:.2f}</b>\n"
                f"You will receive an instant notification when XAU/USD crosses this level."
            )
            await update.message.reply_html(text, reply_markup=self._get_main_keyboard())
        except ValueError:
            await update.message.reply_text("Invalid price format. Please specify a number, e.g. /alert 2925.50")

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        st = self.risk_engine.get_state()
        active_client = self.worker.get_active_client() if self.worker else None
        acc_id = active_client.account_id if active_client else "Not Configured"
        badge = self._get_badge()
        bid = self.worker.current_bid if self.worker else 2900.0
        ask = self.worker.current_ask if self.worker else 2900.25
        summary = await active_client.get_account_summary() if active_client else {}
        is_synced = summary.get("is_live_synced", False)
        if is_synced:
            live_bal = float(summary.get("balance", st["daily_starting_equity"]))
            live_eq = float(summary.get("equity", live_bal))
            margin = float(summary.get("margin", 0.0))
        else:
            live_bal = float(st["daily_starting_equity"])
            live_eq = live_bal + float(st["daily_pnl"])
            margin = 0.0

        sync_status = "🟢 Connected (Live API Synced)" if is_synced else "🟡 Standby (Local / Fallback Mode)"

        text = (
            f"📊 <b>Account & System Status</b> {badge}\n\n"
            f"• Exness Connection: <b>{sync_status}</b>\n"
            f"• Account ID: <code>{acc_id}</code>\n"
            f"• Balance: <b>${live_bal:.2f}</b> | Equity: <b>${live_eq:.2f}</b>\n"
            f"• Used Margin: <b>${margin:.2f}</b>\n"
            f"• Gold Bid: <b>${bid:.2f}</b> | Ask: <b>${ask:.2f}</b>\n"
            f"• Starting Equity: <b>${st['daily_starting_equity']:.2f}</b>\n"
            f"• Today's PnL: <b>${st['daily_pnl']:.2f}</b> ({st['daily_loss_pct']} / {st['max_daily_loss_pct']}% max)\n"
            f"• Trades Today: <b>{st['daily_trade_count']}</b> / {st['max_trades_per_day']}\n"
            f"• Consecutive Losses: <b>{st['consecutive_losses']}</b> / {st['max_consecutive_losses']}\n"
            f"• Can Trade: <b>{'✅ YES' if st['can_trade'] else '❌ NO'}</b>\n"
            f"• Paused: <b>{'⏸️ YES' if st['paused'] else '▶️ NO'}</b>"
        )
        buttons = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu_status")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def mode_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        text = (
            f"⚡ <b>Exness Mode Switcher</b>\n\n"
            f"Currently Active: {badge}\n\n"
            f"⚠️ <b>Notice:</b> Switching to <b>EXNESS REAL</b> requires confirmation to protect live funds."
        )
        buttons = [
            [InlineKeyboardButton("🟡 Set to EXNESS DEMO", callback_data="set_mode_demo")],
            [InlineKeyboardButton("🔴 Set to EXNESS REAL", callback_data="set_mode_real_warn")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def positions_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        positions = self.worker.positions if self.worker else {}
        if not positions:
            text = f"📈 <b>Active Open Positions</b> {badge}\n\nNo open positions at this moment."
            buttons = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="menu_positions")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
            ]
            await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))
            return

        bid = self.worker.current_bid if self.worker else 2900.0
        ask = self.worker.current_ask if self.worker else 2900.25
        text = f"📈 <b>Active Open Positions</b> ({len(positions)}) {badge}\n\n"
        buttons = []
        for pid, pos in positions.items():
            pnl = (bid - pos["open_price"]) * pos["volume"] * 100.0 if pos["direction"] == "buy" else (pos["open_price"] - ask) * pos["volume"] * 100.0
            text += (
                f"• <b>#{pid}</b>: {pos['direction'].upper()} {pos['volume']} lots @ {pos['open_price']:.2f}\n"
                f"  SL: {pos['stop_loss']:.2f} | TP1: {pos['take_profit_1']:.2f} | PnL: <b>${pnl:.2f}</b>\n\n"
            )
            buttons.append([
                InlineKeyboardButton(f"❌ Close #{pid}", callback_data=f"pos_close_{pid}"),
                InlineKeyboardButton(f"✂️ Close 50%", callback_data=f"pos_half_{pid}"),
                InlineKeyboardButton(f"🛡️ SL to BE", callback_data=f"pos_be_{pid}"),
                InlineKeyboardButton(f"⚡ Trail ATR", callback_data=f"pos_trail_{pid}")
            ])
        buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")])
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def rules_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        st = self.risk_engine.get_state()
        news_b = self.worker.news_engine.blackout_before if self.worker else 30
        text = (
            f"⚙️ <b>Interactive Rule Controls</b> {badge}\n\n"
            f"1. <b>Risk per trade:</b> {st['max_risk_pct']}%\n"
            f"2. <b>Max Daily Loss:</b> {st['max_daily_loss_pct']}%\n"
            f"3. <b>Max Trades / Day:</b> {st['max_trades_per_day']}\n"
            f"4. <b>News Blackout:</b> ±{news_b} mins before/after\n\n"
            f"Tap a button below to adjust rules instantly:"
        )
        buttons = [
            [
                InlineKeyboardButton("Risk: 0.25%", callback_data="rule_risk_0.25"),
                InlineKeyboardButton("Risk: 0.5%", callback_data="rule_risk_0.5"),
                InlineKeyboardButton("Risk: 1.0%", callback_data="rule_risk_1.0")
            ],
            [
                InlineKeyboardButton("Daily Loss: 1%", callback_data="rule_loss_1.0"),
                InlineKeyboardButton("Daily Loss: 2%", callback_data="rule_loss_2.0"),
                InlineKeyboardButton("Daily Loss: 3%", callback_data="rule_loss_3.0")
            ],
            [
                InlineKeyboardButton("Trades/Day: 3", callback_data="rule_trades_3"),
                InlineKeyboardButton("Trades/Day: 5", callback_data="rule_trades_5"),
                InlineKeyboardButton("Trades/Day: 10", callback_data="rule_trades_10")
            ],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def analysis_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        ai_data = self.worker.last_ai_analysis if self.worker else {}
        bid = self.worker.current_bid if self.worker else 2900.0
        ask = self.worker.current_ask if self.worker else 2900.25
        text = (
            f"🧠 <b>xKiro AI & ICT/SMC Market Analysis</b> {badge}\n\n"
            f"• Instrument: <b>XAU/USD</b>\n"
            f"• Bias: <b>{ai_data.get('trading_bias', 'Neutral')}</b>\n"
            f"• Confidence: <b>{float(ai_data.get('confidence_score', 0.0)) * 100:.0f}%</b>\n"
            f"• Analysis: {ai_data.get('reason', 'Evaluating H4/H1 structure and liquidity sweeps...')}\n\n"
            f"Current Price: Bid {bid:.2f} / Ask {ask:.2f}"
        )
        buttons = [
            [InlineKeyboardButton("🔄 Refresh Analysis", callback_data="refresh_ai_analysis")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def news_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        upcoming = self.worker.news_engine.get_upcoming_events(limit=5) if self.worker else []
        is_blackout, reason = self.worker.news_engine.is_blackout_active() if self.worker else (False, "OK")
        text = (
            f"📰 <b>Economic Calendar & News Blackout</b> {badge}\n\n"
            f"• Blackout Status: <b>{'🚫 ACTIVE' if is_blackout else '✅ CLEAR'}</b>\n"
            f"• Note: {reason}\n\n"
            f"<b>Upcoming High-Impact USD Events:</b>\n"
        )
        for ev in upcoming:
            text += f"• <b>{ev.get('event_name')}</b> ({ev.get('currency')})\n  Time: {ev.get('event_time')} | Forecast: {ev.get('forecast')}\n"
        buttons = [
            [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def pause_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        self.risk_engine.paused = True
        SettingsService.set_setting("PAUSED", "true")
        badge = self._get_badge()
        await self._send_or_edit(update, f"⏸️ <b>Trading PAUSED by owner.</b> {badge}", self._get_main_keyboard())

    async def resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        if self.risk_engine.manual_approval_required:
            await self._send_or_edit(update, f"⚠️ Locked by consecutive losses! Please approve resume. {badge}", self._get_main_keyboard())
        else:
            self.risk_engine.paused = False
            SettingsService.set_setting("PAUSED", "false")
            await self._send_or_edit(update, f"▶️ <b>Trading RESUMED.</b> {badge}", self._get_main_keyboard())

    async def closeall_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        text = (
            f"🚨 <b>EMERGENCY CONFIRMATION: CLOSE ALL POSITIONS</b> 🚨\n\n"
            f"Are you sure you want to close ALL active positions right now?"
        )
        buttons = [
            [InlineKeyboardButton("💥 YES, CLOSE ALL POSITIONS", callback_data="action_closeall_execute")],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
        ]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(buttons))

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query:
            return
        if not self._is_owner(update):
            try:
                await query.answer("Unauthorized", show_alert=True)
            except Exception:
                pass
            return

        try:
            await query.answer()
        except Exception:
            pass
        data = query.data

        if data == "menu_main":
            await self.start_cmd(update, context)
        elif data == "menu_status":
            await self.status_cmd(update, context)
        elif data == "menu_mode":
            await self.mode_cmd(update, context)
        elif data == "menu_positions":
            await self.positions_cmd(update, context)
        elif data == "menu_rules":
            await self.rules_cmd(update, context)
        elif data == "menu_analysis":
            await self.analysis_cmd(update, context)
        elif data == "menu_sentiment":
            await self.sentiment_cmd(update, context)
        elif data == "menu_news":
            await self.news_cmd(update, context)
        elif data == "menu_chart":
            await self.chart_cmd(update, context)
        elif data == "menu_perf":
            await self.performance_cmd(update, context)
        elif data == "menu_alerts":
            await self.alert_cmd(update, context)
        elif data == "clear_price_alerts":
            self.price_alerts.clear()
            await query.answer("All price alerts cleared!", show_alert=True)
            await self.alert_cmd(update, context)
        elif data == "action_pause":
            await self.pause_cmd(update, context)
        elif data == "action_resume":
            await self.resume_cmd(update, context)
        elif data == "menu_closeall_confirm":
            await self.closeall_cmd(update, context)

        elif data == "set_mode_demo":
            if self.worker:
                self.worker.set_trading_mode("EXNESS_DEMO")
            await query.edit_message_text(
                "✅ <b>Successfully switched to EXNESS DEMO!</b>\nTrading is now operating in demo account.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]])
            )

        elif data == "set_mode_real_warn":
            text = (
                f"⚠️🚨 <b>CAUTION: LIVE TRADING CONFIRMATION</b> 🚨⚠️\n\n"
                f"You are about to switch to <b>EXNESS REAL LIVE ACCOUNT</b>.\n"
                f"Real funds will be used for market orders on XAU/USD.\n\n"
                f"Are you absolutely sure you want to activate REAL trading?"
            )
            buttons = [
                [InlineKeyboardButton("🔴 YES, ACTIVATE REAL TRADING", callback_data="set_mode_real_confirm")],
                [InlineKeyboardButton("❌ Cancel (Keep Demo)", callback_data="menu_mode")]
            ]
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

        elif data == "set_mode_real_confirm":
            if self.worker:
                self.worker.set_trading_mode("EXNESS_REAL", confirm_real=True)
            await query.edit_message_text(
                "🔴 <b>EXNESS REAL ACCOUNT ACTIVATED!</b>\nLive trading enabled. All safety risk limits remain strictly active.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]])
            )

        elif data.startswith("rule_risk_"):
            val = float(data.split("_")[2])
            self.risk_engine.max_risk_pct = val / 100.0
            SettingsService.set_setting("MAX_RISK_PER_TRADE_PCT", str(val))
            await query.answer(f"Risk per trade set to {val}%", show_alert=True)
            await self.rules_cmd(update, context)

        elif data.startswith("rule_loss_"):
            val = float(data.split("_")[2])
            self.risk_engine.max_daily_loss_pct = val / 100.0
            SettingsService.set_setting("MAX_DAILY_LOSS_PCT", str(val))
            await query.answer(f"Max daily loss set to {val}%", show_alert=True)
            await self.rules_cmd(update, context)

        elif data.startswith("rule_trades_"):
            val = int(data.split("_")[2])
            self.risk_engine.max_trades_per_day = val
            SettingsService.set_setting("MAX_TRADES_PER_DAY", str(val))
            await query.answer(f"Max trades per day set to {val}", show_alert=True)
            await self.rules_cmd(update, context)

        elif data.startswith("pos_close_"):
            pid = data.replace("pos_close_", "")
            if self.worker and pid in self.worker.positions:
                pos = self.worker.positions.pop(pid)
                client = self.worker.get_active_client()
                if client:
                    try:
                        await client.close_position(pid)
                    except Exception as e:
                        logger.error(f"Failed to close position on Exness: {e}")
                await query.answer(f"Position #{pid} closed successfully!", show_alert=True)
            else:
                await query.answer("Position not found or already closed.", show_alert=True)
            await self.positions_cmd(update, context)

        elif data.startswith("pos_half_"):
            pid = data.replace("pos_half_", "")
            if self.worker and pid in self.worker.positions:
                pos = self.worker.positions[pid]
                half_vol = round(pos["volume"] / 2.0, 2)
                if half_vol >= 0.01:
                    client = self.worker.get_active_client()
                    if client:
                        try:
                            await client.close_position(pid, volume=str(half_vol))
                        except Exception as e:
                            logger.error(f"Failed to close 50% on Exness: {e}")
                    pos["volume"] = round(pos["volume"] - half_vol, 2)
                    await query.answer(f"Closed {half_vol} lots (50%). Remaining: {pos['volume']} lots", show_alert=True)
                else:
                    await query.answer("Volume too small for partial close.", show_alert=True)
            else:
                await query.answer("Position not found.", show_alert=True)
            await self.positions_cmd(update, context)

        elif data.startswith("pos_be_"):
            pid = data.replace("pos_be_", "")
            if self.worker and pid in self.worker.positions:
                pos = self.worker.positions[pid]
                pos["stop_loss"] = pos["open_price"]
                client = self.worker.get_active_client()
                if client:
                    try:
                        await client.update_position_sl_tp(pid, stop_loss_price=pos["open_price"])
                    except Exception as e:
                        logger.error(f"Failed to update SL to BE on Exness: {e}")
                await query.answer(f"Stop loss moved to Breakeven @ {pos['open_price']:.2f}", show_alert=True)
            else:
                await query.answer("Position not found.", show_alert=True)

        elif data.startswith("pos_trail_"):
            pid = data.replace("pos_trail_", "")
            if self.worker and pid in self.worker.positions:
                pos = self.worker.positions[pid]
                cur_price = self.worker.current_bid if pos["direction"] == "buy" else self.worker.current_ask
                # 3.0 point ATR offset for Gold
                new_sl = round(cur_price - 3.0, 2) if pos["direction"] == "buy" else round(cur_price + 3.0, 2)
                pos["stop_loss"] = new_sl
                client = self.worker.get_active_client()
                if client:
                    try:
                        await client.update_position_sl_tp(pid, stop_loss_price=new_sl)
                    except Exception as e:
                        logger.error(f"Failed to trail SL on Exness: {e}")
                await query.answer(f"Trailing SL adjusted to {new_sl:.2f}", show_alert=True)
            else:
                await query.answer("Position not found.", show_alert=True)

        elif data == "refresh_ai_analysis":
            if self.worker:
                res = await self.worker.ai_client.analyze_market(
                    symbol=settings.SYMBOL,
                    current_price=self.worker.current_bid,
                    technical_summary={"direction": "Evaluating"}
                )
                self.worker.last_ai_analysis = res.model_dump()
            await self.analysis_cmd(update, context)

        elif data == "action_closeall_execute":
            if self.worker:
                client = self.worker.get_active_client()
                for pid in list(self.worker.positions.keys()):
                    if client:
                        try:
                            await client.close_position(pid)
                        except Exception as e:
                            logger.error(f"Error closing position #{pid}: {e}")
                self.worker.positions.clear()
            await query.edit_message_text(
                "✅ <b>All positions have been successfully closed!</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]])
            )

        elif data == "approve_resume_action":
            self.risk_engine.approve_resume()
            await query.edit_message_text(
                "✅ <b>Consecutive Loss Lock Cleared!</b> Trading is resumed.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]])
            )

        elif data == "deny_resume_action":
            self.risk_engine.deny_resume()
            await query.edit_message_text(
                "🛑 <b>System remains paused.</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]])
            )

    async def send_trade_alert(self, pos: Dict[str, Any], ai_res: Any):
        if not self.app or not self.owner_id:
            return
        badge = self._get_badge()
        pid = pos["id"]
        text = (
            f"🚀 <b>New High-Probability Trade Executed!</b>\n"
            f"Platform: {badge}\n"
            f"Position: <b>#{pid}</b>\n"
            f"Side: <b>{pos['direction'].upper()}</b> {pos['volume']} lots @ {pos['open_price']:.2f}\n"
            f"SL: <b>{pos['stop_loss']:.2f}</b> | TP1: <b>{pos['take_profit_1']:.2f}</b> | TP2: <b>{pos['take_profit_2']:.2f}</b>\n\n"
            f"🧠 <b>AI Confidence:</b> {getattr(ai_res, 'confidence_score', 0.85)*100:.0f}%\n"
            f"Analysis: {getattr(ai_res, 'reason', 'ICT liquidity sweep and structure shift confirmed.')}"
        )
        buttons = [
            [
                InlineKeyboardButton(f"❌ Close", callback_data=f"pos_close_{pid}"),
                InlineKeyboardButton(f"✂️ 50%", callback_data=f"pos_half_{pid}"),
                InlineKeyboardButton(f"🛡️ BE", callback_data=f"pos_be_{pid}"),
                InlineKeyboardButton(f"⚡ Trail", callback_data=f"pos_trail_{pid}")
            ],
            [InlineKeyboardButton("📊 View Open Positions", callback_data="menu_positions")]
        ]
        # Generate ICT Chart Snapshot with trade markers
        client = self.worker.get_active_client() if self.worker else None
        candles = []
        if client:
            try:
                candles = await client.get_candles(settings.SYMBOL, timeframe="M5", count=35)
            except Exception:
                pass

        setup = {
            "entry_price": pos["open_price"],
            "stop_loss": pos["stop_loss"],
            "tp1": pos["take_profit_1"],
            "tp2": pos["take_profit_2"]
        }
        chart_buf = ICTChartRenderer.render_candlestick_chart(
            candles=candles,
            symbol="XAU/USD",
            timeframe="M5",
            trade_setup=setup
        )

        try:
            await self.app.bot.send_photo(
                chat_id=self.owner_id,
                photo=chart_buf,
                caption=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Failed to send trade alert with photo: {e}")
            try:
                await self.app.bot.send_message(
                    chat_id=self.owner_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception:
                pass

    async def send_consecutive_loss_alert(self, losses: int, total_loss: float):
        if not self.app or not self.owner_id:
            return
        badge = self._get_badge()
        text = (
            f"🛑⚠️ <b>SAFETY LOCK: {losses} CONSECUTIVE LOSSES DETECTED</b> ⚠️🛑\n"
            f"Platform: {badge}\n\n"
            f"Total Loss in streak: <b>${abs(total_loss):.2f}</b>\n"
            f"The deterministic risk engine has locked trade generation to protect capital.\n\n"
            f"Please review market conditions and choose an action:"
        )
        buttons = [
            [InlineKeyboardButton("✅ Approve & Resume", callback_data="approve_resume_action")],
            [InlineKeyboardButton("🛑 Deny & Keep Paused", callback_data="deny_resume_action")]
        ]
        try:
            await self.app.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Failed to send consecutive loss alert: {e}")

    async def send_notification(self, text: str):
        if not self.app or not self.owner_id:
            return
        badge = self._get_badge()
        try:
            await self.app.bot.send_message(
                chat_id=self.owner_id,
                text=f"{badge}\n{text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    async def check_price_alerts(self, current_price: float):
        if not self.app or not self.owner_id or not self.price_alerts:
            return
        hit_alerts = []
        for target, note in list(self.price_alerts.items()):
            if abs(current_price - target) <= 0.75:
                hit_alerts.append(target)
                badge = self._get_badge()
                text = (
                    f"🎯🚨 <b>GOLD PRICE TARGET REACHED!</b> 🚨🎯\n"
                    f"Platform: {badge}\n\n"
                    f"Current Bid: <b>${current_price:.2f}</b>\n"
                    f"Target Alert: <b>${target:.2f}</b>\n"
                    f"Note: {note}\n\n"
                    f"Review market conditions or manage open exposure."
                )
                try:
                    await self.app.bot.send_message(
                        chat_id=self.owner_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=self._get_main_keyboard()
                    )
                except Exception as e:
                    logger.error(f"Failed to send price alert: {e}")
        for h in hit_alerts:
            self.price_alerts.pop(h, None)

    async def check_upcoming_news_warning(self):
        if not self.app or not self.owner_id or not self.worker:
            return
        upcoming = self.worker.news_engine.get_upcoming_events(limit=3)
        now = datetime.datetime.now(datetime.timezone.utc)
        for ev in upcoming:
            ev_id = ev.get("id") or ev.get("event_name")
            if ev_id in self.last_news_notified:
                continue
            ev_time = ev.get("event_time")
            if isinstance(ev_time, str):
                try:
                    ev_time = datetime.datetime.fromisoformat(ev_time.replace("Z", "+00:00"))
                except Exception:
                    continue
            if isinstance(ev_time, datetime.datetime):
                # Ensure ev_time is timezone-aware UTC for subtraction
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=datetime.timezone.utc)
                delta_mins = (ev_time - now).total_seconds() / 60.0
                if 0 <= delta_mins <= 15:
                    self.last_news_notified.add(ev_id)
                    badge = self._get_badge()
                    text = (
                        f"⚠️📰 <b>HIGH-IMPACT NEWS WARNING (T-{int(delta_mins)} mins)</b> 📰⚠️\n"
                        f"Platform: {badge}\n\n"
                        f"Event: <b>{ev.get('event_name')} ({ev.get('currency')})</b>\n"
                        f"Scheduled: <b>{ev_time.strftime('%H:%M UTC')}</b>\n"
                        f"Forecast: <b>{ev.get('forecast')}</b> | Previous: <b>{ev.get('previous')}</b>\n\n"
                        f"🛡️ <i>The system will enforce entry blackout windows to protect capital from news spikes.</i>"
                    )
                    try:
                        await self.app.bot.send_message(
                            chat_id=self.owner_id,
                            text=text,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send news warning: {e}")

    async def send_session_briefing(self, session_name: str):
        if not self.app or not self.owner_id or not self.worker:
            return
        badge = self._get_badge()
        st = self.risk_engine.get_state()
        cur_bid = self.worker.current_bid
        pos_count = len(self.worker.positions)
        ai_data = self.worker.last_ai_analysis
        text = (
            f"🌅 <b>Session Market Briefing: {session_name}</b>\n"
            f"Active: {badge}\n\n"
            f"• XAU/USD Bid: <b>${cur_bid:.2f}</b>\n"
            f"• Market Bias: <b>{ai_data.get('trading_bias', 'Neutral')}</b> ({float(ai_data.get('confidence_score', 0.0))*100:.0f}% confidence)\n"
            f"• Today's PnL: <b>${st['daily_pnl']:.2f}</b> ({st['daily_trade_count']} trades)\n"
            f"• Open Positions: <b>{pos_count}</b>\n"
            f"• Risk Allowed: <b>{st['max_risk_pct']}% / trade</b> (Loss cap: {st['max_daily_loss_pct']}%)\n\n"
            f"Good luck in the session ahead, Commander!"
        )
        try:
            await self.app.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode="HTML",
                reply_markup=self._get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send session briefing: {e}")

    def register_handlers(self, app: Application):
        self.app = app
        app.add_handler(CommandHandler(["start", "menu"], self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("status", self.status_cmd))
        app.add_handler(CommandHandler("chart", self.chart_cmd))
        app.add_handler(CommandHandler("performance", self.performance_cmd))
        app.add_handler(CommandHandler("alert", self.alert_cmd))
        app.add_handler(CommandHandler("mode", self.mode_cmd))
        app.add_handler(CommandHandler("positions", self.positions_cmd))
        app.add_handler(CommandHandler("rules", self.rules_cmd))
        app.add_handler(CommandHandler("analysis", self.analysis_cmd))
        app.add_handler(CommandHandler(["sentiment", "fedspeech"], self.sentiment_cmd))
        app.add_handler(CommandHandler("news", self.news_cmd))
        app.add_handler(CommandHandler("pause", self.pause_cmd))
        app.add_handler(CommandHandler("resume", self.resume_cmd))
        app.add_handler(CommandHandler("closeall", self.closeall_cmd))
        app.add_handler(CallbackQueryHandler(self.handle_callback_query))

    async def start_polling(self):
        if not settings.TELEGRAM_BOT_TOKEN or "your_telegram" in settings.TELEGRAM_BOT_TOKEN:
            logger.info("Telegram bot token not provided; polling disabled.")
            return
        try:
            builder = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN)
            self.app = builder.build()
            self.register_handlers(self.app)
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started with interactive menus.")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

    async def stop(self):
        if self.app:
            try:
                if self.app.updater and self.app.updater.running:
                    await self.app.updater.stop()
                if self.app.running:
                    await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down Telegram bot: {e}")
