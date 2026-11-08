import base64
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from backend.app.broker.exness.signing import ExnessSigner

logger = logging.getLogger("exness_client")

class ExnessClient:
    """
    Official Exness Trading API Client (v1.0.2 conforming to OpenAPI specification):
    - Uses DNS hostnames: https://api.exness.com (Main) and https://api.exness-api.com (Alternative)
    - Full Ed25519 cryptographic request signing (EXN-API-KEY, EXN-DATA, EXN-SIGN, etc.)
    - Account monetary state & active positions via GET /v1/trading/accounts/{id}/snapshot
    - Market position opening via POST /v1/trading/accounts/{id}/positions
    - Position closing & partial closing via DELETE /v1/trading/accounts/{id}/positions/{id}?volume=...
    - SL/TP order creation via POST /v1/trading/accounts/{id}/orders
    - Async operation confirmation via GET /v1/trading/accounts/{id}/operations/{id}
    - Real-time candle data via GET /v1/market-data/accounts/{id}/candles
    - Real-time instrument quotes via GET /v1/market-data/accounts/{id}/quotes
    """
    DEFAULT_HOSTS = ["https://api.exness.com", "https://api.exness-api.com"]

    def __init__(
        self,
        base_url: Optional[str] = None,
        account_id: str = "",
        api_key: str = "",
        private_key_b64: Optional[str] = None,
        timeout: float = 12.0
    ):
        self.account_id = str(account_id or "").strip()
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout
        self.private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self.last_sync_error: Optional[str] = None
        self.last_sync_time: Optional[float] = None
        self.is_connected: bool = False

        self.base_urls = []
        if base_url and "exness-trader.com" not in base_url:
            self.base_urls.append(base_url.rstrip("/"))
        for host in self.DEFAULT_HOSTS:
            if host not in self.base_urls:
                self.base_urls.append(host)
        self.current_base_url = self.base_urls[0]

        if private_key_b64:
            self.private_key = self._load_private_key(private_key_b64)

    def _load_private_key(self, raw_val: str) -> Optional[ed25519.Ed25519PrivateKey]:
        """Loads Ed25519 private key from PEM, Hex (128 or 64 char), or Base64."""
        if not raw_val:
            return None
        val = raw_val.strip()

        # 1. Try PEM
        if "-----BEGIN" in val:
            try:
                loaded = serialization.load_pem_private_key(val.encode("utf-8"), password=None)
                if isinstance(loaded, ed25519.Ed25519PrivateKey):
                    return loaded
            except Exception as e:
                logger.debug(f"Failed loading PEM key: {e}")

        # 2. Try Hex
        try:
            raw_hex = bytes.fromhex(val)
            if len(raw_hex) in (32, 64):
                return ed25519.Ed25519PrivateKey.from_private_bytes(raw_hex[:32])
        except (ValueError, TypeError):
            pass

        # 3. Try Base64 / DER
        try:
            raw_b64 = base64.b64decode(val)
            if len(raw_b64) in (32, 64):
                return ed25519.Ed25519PrivateKey.from_private_bytes(raw_b64[:32])
            loaded = serialization.load_der_private_key(raw_b64, password=None)
            if isinstance(loaded, ed25519.Ed25519PrivateKey):
                return loaded
        except Exception as e:
            logger.debug(f"Failed loading Base64 key: {e}")

        logger.warning("Could not parse Exness Ed25519 private key.")
        return None

    def _get_headers(self, method: str, path: str, idempotency_key: str = "", body: Optional[Any] = None) -> Dict[str, str]:
        if not self.private_key or not self.api_key:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["EXN-API-KEY"] = self.api_key
            return headers

        return ExnessSigner.sign_request(
            api_key=self.api_key,
            private_key=self.private_key,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
            body=body
        )

    async def _request(self, method: str, path: str, idempotency_key: str = "", body: Optional[Any] = None) -> httpx.Response:
        """Sends signed request with automatic host failover between api.exness.com and api.exness-api.com."""
        last_exception = None
        for base in self.base_urls:
            url = f"{base}{path}"
            headers = self._get_headers(method=method, path=path, idempotency_key=idempotency_key, body=body)
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        resp = await client.get(url, headers=headers)
                    elif method.upper() == "POST":
                        resp = await client.post(url, headers=headers, json=body if body else None)
                    elif method.upper() == "PATCH":
                        resp = await client.patch(url, headers=headers, json=body if body else None)
                    elif method.upper() == "DELETE":
                        resp = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if resp.status_code in [200, 201, 202, 204]:
                        self.current_base_url = base
                        self.is_connected = True
                        self.last_sync_error = None
                        return resp
                    else:
                        logger.warning(f"Exness API returned HTTP {resp.status_code} for {url}: {resp.text[:300]}")
                        resp.raise_for_status()
            except Exception as e:
                last_exception = e
                logger.debug(f"Request failed for host {base}: {e}")

        self.is_connected = False
        self.last_sync_error = str(last_exception)
        raise last_exception or RuntimeError("Exness request failed across all hosts")

    async def get_trading_snapshot(self) -> Dict[str, Any]:
        """Fetch trading snapshot containing account_state, open orders, and open positions."""
        if not self.account_id:
            return {}
        path = f"/v1/trading/accounts/{self.account_id}/snapshot"
        resp = await self._request("GET", path)
        return resp.json()

    async def get_account_summary(self) -> Dict[str, Any]:
        """Fetch real-time account monetary balance, equity, and margin from Exness."""
        if not self.account_id:
            return {
                "account_id": "NOT_CONFIGURED",
                "balance": 0.0,
                "equity": 0.0,
                "margin": 0.0,
                "free_margin": 0.0,
                "currency": "USD",
                "leverage": "1:2000",
                "status": "UNCONFIGURED",
                "is_live_synced": False
            }

        try:
            snapshot = await self.get_trading_snapshot()
            acct_state = snapshot.get("account_state", {})
            balance = float(acct_state.get("balance", 0.0))
            equity = float(acct_state.get("equity", balance))
            margin = float(acct_state.get("used_margin", 0.0))
            free_margin = max(0.0, equity - margin)
            return {
                "account_id": self.account_id,
                "balance": balance,
                "equity": equity,
                "margin": margin,
                "free_margin": free_margin,
                "currency": "USD",
                "leverage": "1:2000",
                "status": "ACTIVE",
                "is_live_synced": True
            }
        except Exception as e:
            logger.debug(f"Snapshot query failed: {e}")

        try:
            path = f"/v1/configuration/accounts/{self.account_id}/account"
            resp = await self._request("GET", path)
            data = resp.json()
            balance = float(data.get("balance", 0.0))
            equity = float(data.get("equity", balance))
            margin = float(data.get("margin", 0.0))
            return {
                "account_id": self.account_id,
                "balance": balance,
                "equity": equity,
                "margin": margin,
                "free_margin": max(0.0, equity - margin),
                "currency": data.get("currency", "USD"),
                "leverage": data.get("leverage", "1:2000"),
                "status": data.get("account_status", "ACTIVE"),
                "is_live_synced": True
            }
        except Exception as e:
            logger.warning(f"Exness account sync failed: {e}")

        return {
            "account_id": self.account_id,
            "balance": 0.0,
            "equity": 0.0,
            "margin": 0.0,
            "free_margin": 0.0,
            "currency": "USD",
            "leverage": "1:2000",
            "status": "DISCONNECTED",
            "last_error": str(self.last_sync_error),
            "is_live_synced": False
        }

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch active open positions directly from official snapshot."""
        if not self.account_id:
            return []
        try:
            snapshot = await self.get_trading_snapshot()
            return snapshot.get("positions", [])
        except Exception as e:
            logger.warning(f"Exness get_open_positions failed: {e}")
            return []

    async def open_position(
        self,
        symbol: str,
        side: str,
        volume: str,
        stop_loss_price: Optional[str] = None,
        take_profit_price: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Open position with immediate market execution via POST /v1/trading/accounts/{id}/positions.
        Exness returns ACK with operation_id. We await confirmed status.
        """
        path = f"/v1/trading/accounts/{self.account_id}/positions"
        body = {
            "instrument": symbol,
            "side": side.lower(),
            "volume": str(volume)
        }
        if stop_loss_price:
            body["stop_loss_price"] = str(stop_loss_price)
        if take_profit_price:
            body["take_profit_price"] = str(take_profit_price)

        resp = await self._request("POST", path, idempotency_key=f"gh-{uuid.uuid4().hex[:12]}", body=body)
        ack = resp.json()
        op_id = ack.get("operation_id")
        if op_id:
            confirmed_op = await self.poll_operation_status(op_id)
            return {"ack": ack, "operation": confirmed_op}
        return ack

    async def close_position(self, position_id: str, volume: Optional[str] = None) -> Dict[str, Any]:
        """
        Closes position (or partially closes with volume) via DELETE /v1/trading/accounts/{id}/positions/{id}.
        """
        path = f"/v1/trading/accounts/{self.account_id}/positions/{position_id}"
        if volume:
            path += f"?volume={volume}"
        resp = await self._request("DELETE", path, idempotency_key=f"gh-{uuid.uuid4().hex[:12]}")
        ack = resp.json()
        op_id = ack.get("operation_id")
        if op_id:
            confirmed_op = await self.poll_operation_status(op_id)
            return {"ack": ack, "operation": confirmed_op}
        return ack

    async def update_position_sl_tp(
        self,
        position_id: str,
        stop_loss_price: Optional[str] = None,
        take_profit_price: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sets SL/TP for position using an SLTP order via POST /v1/trading/accounts/{id}/orders.
        """
        path = f"/v1/trading/accounts/{self.account_id}/orders"
        body = {
            "order_type": "sltp",
            "position_id": str(position_id)
        }
        if stop_loss_price is not None:
            body["stop_loss_price"] = str(stop_loss_price)
        if take_profit_price is not None:
            body["take_profit_price"] = str(take_profit_price)

        resp = await self._request("POST", path, idempotency_key=f"gh-{uuid.uuid4().hex[:12]}", body=body)
        return resp.json()

    async def poll_operation_status(self, operation_id: str, max_retries: int = 5, delay: float = 0.5) -> Dict[str, Any]:
        """Polls GET /v1/trading/accounts/{id}/operations/{id} until confirmed, rejected, or failed."""
        path = f"/v1/trading/accounts/{self.account_id}/operations/{operation_id}"
        for _ in range(max_retries):
            try:
                resp = await self._request("GET", path)
                data = resp.json()
                status = data.get("status")
                if status in ["confirmed", "rejected", "failed"]:
                    return data
            except Exception as e:
                logger.debug(f"Error polling operation {operation_id}: {e}")
            await asyncio.sleep(delay)
        return {"operation_id": operation_id, "status": "pending_timeout"}

    async def get_quote(self, symbol: str = "XAUUSD") -> Dict[str, float]:
        """Fetch latest bid/ask quote directly from Exness market data endpoint."""
        symbols_to_try = [symbol]
        if "XAUUSD" in symbol and "m" not in symbol:
            symbols_to_try.append(symbol + "m")
        elif "m" in symbol:
            symbols_to_try.append(symbol.replace("m", ""))

        if self.account_id:
            for sym in symbols_to_try:
                path = f"/v1/market-data/accounts/{self.account_id}/quotes?instrument={sym}"
                try:
                    resp = await self._request("GET", path)
                    data = resp.json()
                    bid = float(data.get("bid", 0.0))
                    ask = float(data.get("ask", 0.0))
                    if bid > 0 and ask > 0:
                        return {"bid": bid, "ask": ask}
                except Exception:
                    pass

        return {"bid": 0.0, "ask": 0.0}

    async def get_candles(self, symbol: str = "XAUUSD", timeframe: str = "M5", count: int = 60) -> List[Dict[str, Any]]:
        """Fetch historical candles directly from Exness market data endpoint."""
        symbols_to_try = [symbol]
        if "XAUUSD" in symbol and "m" not in symbol:
            symbols_to_try.append(symbol + "m")

        if self.account_id:
            for sym in symbols_to_try:
                path = f"/v1/market-data/accounts/{self.account_id}/candles?instrument={sym}&timeframe={timeframe}&price_type=bid&count={count}"
                try:
                    resp = await self._request("GET", path)
                    candles = resp.json().get("candles", [])
                    if candles:
                        return candles
                except Exception:
                    pass

        return []
