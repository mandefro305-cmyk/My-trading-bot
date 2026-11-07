import base64
import uuid
import logging
from typing import Dict, Any, List, Optional
import httpx
from cryptography.hazmat.primitives.asymmetric import ed25519
from backend.app.broker.exness.signing import ExnessSigner

logger = logging.getLogger("exness_client")

class ExnessClient:
    def __init__(
        self,
        base_url: str,
        account_id: str,
        api_key: str,
        private_key_b64: Optional[str] = None,
        timeout: float = 15.0
    ):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.api_key = api_key
        self.timeout = timeout
        self.private_key = None

        if private_key_b64:
            try:
                key_bytes = base64.b64decode(private_key_b64)
                if len(key_bytes) == 32:
                    self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)
                else:
                    self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
            except Exception as e:
                logger.error(f"Failed to load Ed25519 private key: {e}")

    def _get_headers(self, method: str, path: str, idempotency_key: str = "", body: Optional[Any] = None) -> Dict[str, str]:
        if not self.private_key:
            raise ValueError("Private key is required to sign Exness API requests.")
        return ExnessSigner.sign_request(
            api_key=self.api_key,
            private_key=self.private_key,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
            body=body
        )

    async def get_candles(self, symbol: str = "XAUUSD", timeframe: str = "M5", count: int = 100) -> List[Dict[str, Any]]:
        path = f"/v1/market-data/accounts/{self.account_id}/candles?instrument={symbol}&timeframe={timeframe}&price_type=bid&count={count}"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}{path}", headers=headers)
            resp.raise_for_status()
            return resp.json().get("candles", [])

    async def open_position(self, symbol: str, side: str, volume: str) -> Dict[str, Any]:
        path = f"/v1/trading/accounts/{self.account_id}/positions"
        body = {"instrument": symbol, "side": side.lower(), "volume": str(volume)}
        headers = self._get_headers("POST", path, idempotency_key=f"gh-{uuid.uuid4().hex[:12]}", body=body)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}{path}", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def close_position(self, position_id: str, volume: Optional[str] = None) -> Dict[str, Any]:
        path = f"/v1/trading/accounts/{self.account_id}/positions/{position_id}"
        if volume:
            path += f"?volume={volume}"
        headers = self._get_headers("DELETE", path, idempotency_key=f"gh-{uuid.uuid4().hex[:12]}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(f"{self.base_url}{path}", headers=headers)
            resp.raise_for_status()
            return resp.json()
