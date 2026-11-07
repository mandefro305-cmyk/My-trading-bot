import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from backend.app.config.settings import settings

logger = logging.getLogger("telegram_bot")

class TelegramControlBot:
    def __init__(self, risk_engine, worker_service=None):
        self.risk_engine = risk_engine
        self.worker = worker_service
        self.owner_id = settings.TELEGRAM_OWNER_ID
        self.app = None

    def _get_badge(self) -> str:
        mode = settings.TRADING_MODE
        if mode == "EXNESS_REAL":
            return "🔴 [EXNESS REAL]"
        elif mode == "EXNESS_DEMO":
            return "🟡 [EXNESS DEMO]"
        return "🟢 [PAPER TRADING]"

    def _is_owner(self, update: Update) -> bool:
        if not self.owner_id:
            return True
        return update.effective_user.id == self.owner_id

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        await update.message.reply_html(
            f"🦅 <b>GoldHunter AI v2.0 Control Center</b>\n"
            f"Platform: <b>{badge}</b>\n\n"
            f"Use /help to view all available commands."
        )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        await update.message.reply_html(
            f"📋 <b>Available Commands</b> ({badge}):\n"
            f"/status - System health, broker & risk state\n"
            f"/balance - Verified broker/paper balance\n"
            f"/positions - Open positions & SL/TP targets\n"
            f"/pause - Pause opening new positions\n"
            f"/resume - Resume opening new positions\n"
            f"/approve_resume - Unlock system after consecutive losses\n"
            f"/deny_resume - Keep system locked in paused state\n"
            f"/closeall - Emergency close all open positions"
        )

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        st = self.risk_engine.get_state()
        await update.message.reply_html(
            f"⚡ <b>Status</b> ({badge})\n"
            f"Can Trade: <b>{st['can_trade']}</b> | Paused: <b>{st['paused']}</b>\n"
            f"Daily PnL: <b>${st['daily_pnl']:.2f}</b> ({st['daily_loss_pct']}%) | Daily Trades: <b>{st['daily_trade_count']}</b>\n"
            f"Consecutive Losses: <b>{st['consecutive_losses']}</b> / 2 max\n"
            f"Manual Lock: <b>{st['manual_approval_required']}</b>"
        )

    async def balance_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        st = self.risk_engine.get_state()
        await update.message.reply_html(
            f"💰 <b>Balance & Equity</b> ({badge})\n"
            f"Starting Balance: <b>${st['daily_starting_equity']:.2f}</b>\n"
            f"Current Daily PnL: <b>${st['daily_pnl']:.2f}</b>"
        )

    async def pause_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        self.risk_engine.paused = True
        badge = self._get_badge()
        await update.message.reply_html(f"⏸️ <b>Trading PAUSED</b> by owner. ({badge})")

    async def resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        if self.risk_engine.manual_approval_required:
            await update.message.reply_html(f"⚠️ Locked by consecutive losses. Use /approve_resume. ({badge})")
            return
        self.risk_engine.paused = False
        await update.message.reply_html(f"▶️ <b>Trading RESUMED</b>. ({badge})")

    async def approve_resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        ok = self.risk_engine.approve_resume()
        await update.message.reply_html(f"✅ <b>Resume APPROVED</b>. Trading unlocked! ({badge})" if ok else f"❌ Approval failed. ({badge})")

    async def deny_resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            return
        badge = self._get_badge()
        self.risk_engine.deny_resume()
        await update.message.reply_html(f"🛑 <b>Resume DENIED</b>. System remains paused. ({badge})")

    async def send_notification(self, text: str):
        if not self.app or not self.owner_id:
            return
        try:
            badge = self._get_badge()
            await self.app.bot.send_message(chat_id=self.owner_id, text=f"{badge}\n{text}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def register_handlers(self, app: Application):
        self.app = app
        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("status", self.status_cmd))
        app.add_handler(CommandHandler("balance", self.balance_cmd))
        app.add_handler(CommandHandler("pause", self.pause_cmd))
        app.add_handler(CommandHandler("resume", self.resume_cmd))
        app.add_handler(CommandHandler("approve_resume", self.approve_resume_cmd))
        app.add_handler(CommandHandler("deny_resume", self.deny_resume_cmd))
