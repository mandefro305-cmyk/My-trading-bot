import pytest
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from backend.app.broker.exness.signing import ExnessSigner
from backend.app.broker.exness.client import ExnessClient
from backend.app.risk.engine import RiskEngine
from backend.app.risk.partial_profit import PartialProfitEngine
from backend.app.services.settings_service import SettingsService
from backend.app.telegram.bot import TelegramControlBot

def test_ed25519_request_signing():
    private_key = ed25519.Ed25519PrivateKey.generate()
    headers = ExnessSigner.sign_request(
        api_key="test-api-key",
        private_key=private_key,
        method="POST",
        path="/v1/trading/accounts/12345/positions",
        idempotency_key="idemp-12345",
        body={"instrument": "XAUUSD", "side": "buy", "volume": "0.1"}
    )
    assert "EXN-API-KEY" in headers
    assert "EXN-SIGN" in headers
    assert "EXN-TIMESTAMP" in headers
    assert headers["EXN-API-KEY"] == "test-api-key"

def test_exness_client_initialization_demo_real():
    priv = ed25519.Ed25519PrivateKey.generate()
    raw = priv.private_bytes_raw()
    b64_key = base64.b64encode(raw).decode()

    client = ExnessClient(
        base_url="https://api.exness-trader.com",
        account_id="ex-demo-999",
        api_key="demo-key",
        private_key_b64=b64_key
    )
    assert client.account_id == "ex-demo-999"
    assert client.private_key is not None

def test_risk_consecutive_losses_and_recovery():
    engine = RiskEngine(max_consecutive_losses=2)
    assert engine.can_open_new_trade() is True

    # 1st loss
    engine.record_trade_result(-50.0)
    assert engine.consecutive_losses == 1
    assert engine.can_open_new_trade() is True

    # 2nd loss -> lock triggered
    engine.record_trade_result(-60.0)
    assert engine.consecutive_losses == 2
    assert engine.manual_approval_required is True
    assert engine.can_open_new_trade() is False

    # Owner manual approval unlocks trading
    approved = engine.approve_resume()
    assert approved is True
    assert engine.manual_approval_required is False
    assert engine.consecutive_losses == 0
    assert engine.can_open_new_trade() is True

def test_partial_profit_taking_3_stages():
    pp = PartialProfitEngine()
    pos = {
        "id": "POS-100",
        "symbol": "XAUUSD",
        "direction": "buy",
        "volume": 1.0,
        "initial_volume": 1.0,
        "original_volume": 1.0,
        "open_price": 2900.0,
        "stop_loss": 2890.0,
        "take_profit_1": 2910.0, # 1R
        "take_profit_2": 2920.0, # 2R
        "take_profit_3": 2930.0, # 3R
        "tp1_hit": False,
        "tp2_hit": False
    }

    # At 2911.0, TP1 should hit (close 40% = 0.4 lots, move SL to breakeven)
    actions = pp.check_position(pos, current_bid=2911.0, current_ask=2911.25)
    assert len(actions) == 1
    assert actions[0]["action"] == "CLOSE_PARTIAL"
    assert actions[0]["stage"] == "TP1"
    assert actions[0]["volume"] == 0.40
    assert actions[0]["move_sl_to_be"] is True

def test_settings_persistence_and_telegram_bot_badge():
    SettingsService.set_setting("TRADING_MODE", "EXNESS_DEMO")
    SettingsService.set_setting("MAX_RISK_PER_TRADE_PCT", "0.75")
    s = SettingsService.get_all_settings()
    assert s["trading_mode"] == "EXNESS_DEMO"
    assert s["max_risk_pct"] == 0.75

    bot = TelegramControlBot(RiskEngine())
    assert "DEMO" in bot._get_badge()
