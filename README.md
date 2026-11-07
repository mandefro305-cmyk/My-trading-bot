# 🦅 GoldHunter AI v2.0 — Master Manual & Deployment Guide

GoldHunter AI is a cloud-hosted, AI-assisted automated XAU/USD (Gold) trading platform designed for continuous, high-reliability operation on **Sevalla**.

---

## 🌟 Key Capabilities
- **Official Exness Trading API Integration**: Full Ed25519 cryptographic request signing protocol (`EXN-*` headers: `EXN-API-KEY`, `EXN-TIMESTAMP`, `EXN-DATA`, `EXN-SIGN`, `EXN-SIGN-VERSION`, `EXN-IDEMPOTENCY-KEY`).
- **3 Execution Modes**:
  1. `PAPER`: Internal simulated execution using live or simulated market feeds.
  2. `EXNESS_DEMO`: Orders routed to your Exness Demo account via the official Exness Trading API.
  3. `EXNESS_REAL`: Direct live trading on Exness with multi-layer risk interlocks (`TRADING_MODE=EXNESS_REAL`, `LIVE_TRADING_ENABLED=true`, `EXNESS_CONFIRM_REAL_TRADING=true`).
- **Deterministic Risk Management Engine**:
  - `MAX_RISK_PER_TRADE`: 0.5% of Account Equity (conservative lot floor sizing).
  - `MAX_DAILY_LOSS`: 2.0% daily circuit breaker.
  - `MAX_TRADES_PER_DAY`: 5 trades.
  - `MAX_CONSECUTIVE_LOSSES`: 2 losses lock the system in `MANUAL_APPROVAL_REQUIRED` state.
- **Structured 3-Stage Partial Profit-Taking**:
  - **TP1 @ 1R**: Closes 40% of initial volume & moves Stop Loss to Break-Even.
  - **TP2 @ 2R**: Closes 30% of initial volume.
  - **TP3 @ 3R**: Closes final 30% volume.
- **xKiro AI Intelligence Subsystem**:
  - Primary Model: `qwen/qwen3.7-max:free`
  - Fallback Model: `qwen/qwen3.7-flash:free`
  - Enforced structured JSON schema for market direction and bias. AI can never override the deterministic risk engine.
- **USD Economic Calendar & News Blackout**:
  - Automatically avoids new entries 30 minutes before and after high-impact events (CPI, NFP, FOMC, PPI, PCE).
- **Private Telegram Control Center**:
  - Owner-only command bot: `/start`, `/status`, `/balance`, `/positions`, `/pause`, `/resume`, `/approve_resume`, `/deny_resume`, `/closeall`.
  - Platform badges (`[EXNESS REAL]`, `[EXNESS DEMO]`, `[PAPER TRADING]`).
- **React Web Dashboard**:
  - Real-time TradingView Lightweight Charts (M5 candlesticks, FVG & liquidity sweep overlays, account metrics, and AI feed).

---

## 🚀 Step-by-Step Sevalla Deployment Guide

Deploying GoldHunter AI on [Sevalla](https://sevalla.com/) requires 3 core components:
1. **Managed PostgreSQL Database**
2. **GoldHunter AI Web Application & REST API**
3. **GoldHunter AI Background Worker Service**

### Step 1: Create Sevalla Managed PostgreSQL
1. Log in to your [Sevalla Dashboard](https://sevalla.com/).
2. Navigate to **Databases** > **Create Database**.
3. Select **PostgreSQL 16**.
4. Choose your preferred region and tier.
5. Once provisioned, copy the **Internal Connection String** (e.g., `postgresql://user:password@host.internal:5432/goldhunter`).

### Step 2: Push Repository to GitHub
1. Create a private GitHub repository: `goldhunter-ai`.
2. Push your project code:
   ```bash
   git remote add origin https://github.com/<your-username>/goldhunter-ai.git
   git branch -M main
   git push -u origin main
   ```

### Step 3: Deploy the Web Application on Sevalla
1. On Sevalla, click **Applications** > **New Application**.
2. Connect your GitHub account and select the `goldhunter-ai` repository.
3. Select **Docker build** (using the root `Dockerfile`).
4. Set the **Port** to `8000`.
5. Under **Environment Variables**, add the variables detailed in `.env.example`:
   - `DATABASE_URL`: Your Sevalla PostgreSQL connection string.
   - `TRADING_MODE`: `PAPER`, `EXNESS_DEMO`, or `EXNESS_REAL`.
   - `EXNESS_API_KEY`: Your official Exness API key.
   - `EXNESS_PRIVATE_KEY_B64`: Your Ed25519 private key (Base64 encoded).
   - `EXNESS_ACCOUNT_ID`: Your Exness trading account number.
   - `EXNESS_MOCK_MODE`: `false` (when using live credentials) or `true`.
   - `XKIRO_API_KEY`: Your xKiro API key.
   - `TELEGRAM_BOT_TOKEN`: Token obtained from `@BotFather`.
   - `TELEGRAM_OWNER_ID`: Your numeric Telegram user ID (from `@userinfobot`).
6. Click **Deploy**. Sevalla will build and launch your application.

### Step 4: Configure the Background Worker
The worker operates as a persistent daemon. On Sevalla:
1. In your application settings, configure a background worker process:
   ```bash
   python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. Enable Sevalla health checks on `/health`.

---

## 📱 Telegram Bot Setup & Commands

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, name your bot `GoldHunter AI`, and save the API token.
3. Message `@userinfobot` to retrieve your numeric user ID.
4. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_ID` in your Sevalla environment variables.
5. Open your bot in Telegram and send `/start`.

### Operational Commands:
- `/status` — View current trading status, daily PnL, consecutive loss counter, and active mode.
- `/balance` — View starting balance and daily realized equity.
- `/positions` — Inspect open positions, lots, stop losses, and take profit targets.
- `/pause` — Pause new trade entries (existing positions continue to be monitored).
- `/resume` — Unpause trading.
- `/approve_resume` — Unlock the system if halted after 2 consecutive losses.
- `/deny_resume` — Keep system in safety pause.
- `/closeall` — Emergency market closure for all active positions.

---

## 💻 Local Development Setup

To run locally with SQLite and the built-in Mock Exness simulator:

```bash
# 1. Clone repository
git clone https://github.com/<your-username>/goldhunter-ai.git
cd goldhunter-ai

# 2. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. Initialize SQLite database
python3 backend/app/database/init_db.py

# 4. Start Backend API & Worker
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start Frontend Dashboard (in a separate terminal)
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to interact with your dashboard!
