import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from backend.app.broker.exness.signing import ExnessSigner
from backend.app.risk.engine import RiskEngine
from backend.app.risk.partial_profit import PartialProfitEngine
from backend.app.strategy.ict_smc.strategy import MultiTimeframeStrategyEngine
from backend.app.strategy.ict_smc.indicators import TechnicalIndicators
from backend.app.broker.exness.mock_gateway import MockExnessGateway

def test_exness_ed25519_signature():
    priv = ed25519.Ed25519PrivateKey.generate()
    headers = ExnessSigner.sign_request(
        api_key="key-123",
        private_key=priv,
        method="POST",
        path="/v1/trading/accounts/123/orders",
        idempotency_key="idemp-123",
        body={"instrument": "XAUUSD"}
    )
    assert headers["EXN-API-KEY"] == "key-123"
    assert headers["EXN-IDEMPOTENCY-KEY"] == "idemp-123"
    assert headers["EXN-SIGN-VERSION"] == "1"

def test_risk_and_position_sizing():
    risk = RiskEngine()
    ok, lots, msg = risk.calculate_position_size(equity=10000.0, entry_price=2900.0, stop_loss=2890.0)
    assert ok is True
    assert lots > 0.0

    # Consecutive loss lock
    risk.record_trade_result(-50.0)
    assert risk.manual_approval_required is False
    risk.record_trade_result(-50.0)
    assert risk.manual_approval_required is True

    # Approve resume
    assert risk.approve_resume() is True
    assert risk.manual_approval_required is False

def test_partial_profit_targets():
    pp = PartialProfitEngine()
    targets = pp.calculate_targets(entry_price=2900.0, stop_loss=2890.0, direction="buy")
    assert targets["tp1"] == 2910.0
    assert targets["tp2"] == 2920.0
    assert targets["tp3"] == 2930.0

@pytest.mark.asyncio
async def test_mock_gateway_candles_and_orders():
    gw = MockExnessGateway(base_price=2900.0)
    candles = await gw.get_candles(count=25)
    assert len(candles) == 25
    assert candles[0]["open"] > 0
