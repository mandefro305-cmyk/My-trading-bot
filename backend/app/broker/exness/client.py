import base64
import uuid
import logging
import asyncio
import time
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
    - Rate-limit protection: Exponential backoff on HTTP 429 and response caching
    - Account monetary state & active positions via GET /v1/trading/accounts/{id}/snapshot
    - Market position opening via POST /v1/trading/accounts/{id}/positions
    - Position closing & partial closing via DELETE /v1/trading/accounts/{id}/positions/{id}?volume=...
    - SL/TP order creation via POST /v1/trading/accounts/{id}/orders
    - Async operation confirmation via GET /v1/trading/accounts/{id}/operations/{id}
    - Real-time candle data via GET /v1/market-data/accounts/{id}/candles
    - Real-time instrument quotes via GET /v1/market-data/accounts/{id}/quotes
    """
    GATEWAY_HOSTS = ["https://api.exness-api.com", "https://api.exness.com"]

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

        # Access point dynamic discovery & caching
        self.discovered_access_point: Optional[str] = None
        self.last_discovery_time: float = 0.0

        # Backoff & rate limit handling
        self.rate_limit_backoff_until: float = 0.0
        self.backoff_duration: float = 30.0

        # Caching to avoid hammering broker endpoints
        self._cached_quote: Dict[str, Any] = {}
        self._quote_cache_time: float = 0.0
        self._cached_candles: Dict[str, Any] = {}
        self._candles_cache_time: Dict[str, float] = {}

        self.gateway_hosts = []
        if base_url and "exness-trader.com" not in base_url:
            self.gateway_hosts.append(base_url.rstrip("/"))
        for host in self.GATEWAY_HOSTS:
            if host not in self.gateway_hosts:
                self.gateway_hosts.append(host)
        self.current_base_url = self.gateway_hosts[0]

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

    async def discover_access_point(self, force_refresh: bool = False) -> str:
        """
        Resolves the dedicated regional Access Point host for the trading account.
        Calls GET /v1/trading/access-point?account_id={account_id} on the Gateway host.
        Caches the resolved Access Point for 1 hour to prevent discovery rate-limiting.
        """
        now = time.time()
        if not force_refresh and self.discovered_access_point and (now - self.last_discovery_time) < 3600:
            return self.discovered_access_point

        if not self.account_id or not self.private_key or not self.api_key:
            return self.gateway_hosts[0]

        discovery_path = f"/v1/trading/access-point?account_id={self.account_id}"
        headers = self._get_headers(method="GET", path=discovery_path, idempotency_key="")

        last_err = None
        for host in self.gateway_hosts:
            url = f"{host}{discovery_path}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        ap = data.get("access_point")
                        if ap and isinstance(ap, str):
                            self.discovered_access_point = ap.rstrip("/")
                            self.last_discovery_time = now
                            self.current_base_url = self.discovered_access_point
                            logger.info(f"Discovered Exness Access Point for account {self.account_id}: {self.discovered_access_point}")
                            return self.discovered_access_point
                    elif resp.status_code == 429:
                        logger.warning(f"Exness Gateway returned 429 during access point discovery on {host}")
                    else:
                        logger.debug(f"Exness Gateway discovery returned HTTP {resp.status_code} on {host}: {resp.text[:150]}")
            except Exception as e:
                last_err = e
                logger.debug(f"Discovery failed on gateway host {host}: {e}")

        # Fallback to configured gateway if discovery couldn't resolve
        fallback = self.discovered_access_point or self.gateway_hosts[0]
        return fallback

    async def _request(self, method: str, path: str, idempotency_key: str = "", body: Optional[Any] = None) -> httpx.Response:
        """Sends signed request with rate limit backoff and dynamic access point routing."""
        now = time.time()
        if now < self.rate_limit_backoff_until:
            wait_remaining = int(self.rate_limit_backoff_until - now)
            raise RuntimeError(f"Exness rate limit backoff active ({wait_remaining}s remaining)")

        # Always ensure Access Point is discovered for account requests
        target_host = await self.discover_access_point()
        hosts_to_try = [target_host]
        for g in self.gateway_hosts:
            if g not in hosts_to_try:
                hosts_to_try.append(g)

        last_exception = None
        for base in hosts_to_try:
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
                        self.backoff_duration = 30.0  # Reset backoff on success
                        return resp
                    elif resp.status_code == 429:
                        # Rate limit triggered: backoff
                        self.rate_limit_backoff_until = time.time() + self.backoff_duration
                        logger.warning(f"Exness returned HTTP 429 (Rate Limited). Pausing requests for {self.backoff_duration}s.")
                        self.backoff_duration = min(300.0, self.backoff_duration * 2)
                        resp.raise_for_status()
                    elif resp.status_code == 404 and base == target_host and self.discovered_access_point:
                        # Access point might be stale or path changed
                        logger.debug(f"404 received on Access Point {base}{path}")
                        resp.raise_for_status()
                    else:
                        logger.debug(f"Exness API returned HTTP {resp.status_code} for {url}")
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
            logger.debug(f"Snapshot query note: {e}")

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
            logger.debug(f"Exness account sync note: {e}")

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
            logger.debug(f"Exness get_open_positions note: {e}")
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
        Closes position via DELETE /v1/trading/accounts/{id}/positions/{id}.
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

    async def poll_operation_status(self, operation_id: str, max_retries: int = 4, delay: float = 1.0) -> Dict[str, Any]:
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
        """Fetch latest bid/ask quote directly from Exness with short caching."""
        now = time.time()
        if self._cached_quote and (now - self._quote_cache_time) < 10.0:
            return self._cached_quote

        symbols_to_try = [symbol]
        if "XAUUSD" in symbol and "m" not in symbol:
            symbols_to_try.append(symbol + "m")
        elif "m" in symbol:
            symbols_to_try.append(symbol.replace("m", ""))

        if self.account_id and now > self.rate_limit_backoff_until:
            for sym in symbols_to_try:
                path = f"/v1/market-data/accounts/{self.account_id}/quotes?instrument={sym}"
                try:
                    resp = await self._request("GET", path)
                    data = resp.json()
                    bid = float(data.get("bid", 0.0))
                    ask = float(data.get("ask", 0.0))
                    if bid > 0 and ask > 0:
                        self._cached_quote = {"bid": bid, "ask": ask}
                        self._quote_cache_time = now
                        return self._cached_quote
                except Exception:
                    pass

        return self._cached_quote or {"bid": 0.0, "ask": 0.0}

    async def get_candles(self, symbol: str = "XAUUSD", timeframe: str = "M5", count: int = 60) -> List[Dict[str, Any]]:
        """Fetch historical candles directly from Exness with 30-second caching."""
        now = time.time()
        cache_key = f"{symbol}_{timeframe}_{count}"
        if cache_key in self._cached_candles and (now - self._candles_cache_time.get(cache_key, 0.0)) < 30.0:
            return self._cached_candles[cache_key]

        symbols_to_try = [symbol]
        if "XAUUSD" in symbol and "m" not in symbol:
            symbols_to_try.append(symbol + "m")

        if self.account_id and now > self.rate_limit_backoff_until:
            for sym in symbols_to_try:
                path = f"/v1/market-data/accounts/{self.account_id}/candles?instrument={sym}&timeframe={timeframe}&price_type=bid&count={count}"
                try:
                    resp = await self._request("GET", path)
                    candles = resp.json().get("candles", [])
                    if candles:
                        self._cached_candles[cache_key] = candles
                        self._candles_cache_time[cache_key] = now
                        return candles
                except Exception:
                    pass

        return self._cached_candles.get(cache_key, [])
