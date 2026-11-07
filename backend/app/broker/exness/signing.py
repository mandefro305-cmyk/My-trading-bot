import base64
import hashlib
import json
import time
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519

class ExnessSigner:
    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _base64url_decode(data: str) -> bytes:
        rem = len(data) % 4
        if rem > 0:
            data += "=" * (4 - rem)
        return base64.urlsafe_b64decode(data)

    @classmethod
    def calculate_body_hash(cls, body: Optional[Any]) -> str:
        if body is None or body == "" or body == b"":
            data = b""
        elif isinstance(body, dict):
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        sha = hashlib.sha256(data).digest()
        return cls._base64url_encode(sha)

    @classmethod
    def sign_request(
        cls,
        api_key: str,
        private_key: ed25519.Ed25519PrivateKey,
        method: str,
        path: str,
        idempotency_key: str = "",
        body: Optional[Any] = None,
        timestamp_ms: Optional[int] = None
    ) -> Dict[str, str]:
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        method = method.upper()
        if method == "GET":
            idempotency_key = ""

        body_hash = cls.calculate_body_hash(body)

        payload_obj = {
            "api_key": api_key,
            "idempotency_key": idempotency_key,
            "timestamp": timestamp_ms,
            "sign_version": 1,
            "method": method,
            "path": path,
            "body_hash": body_hash
        }

        payload_bytes = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
        exn_data = cls._base64url_encode(payload_bytes)
        signature = private_key.sign(payload_bytes)
        exn_sign = cls._base64url_encode(signature)

        headers = {
            "EXN-API-KEY": api_key,
            "EXN-IDEMPOTENCY-KEY": idempotency_key,
            "EXN-TIMESTAMP": str(timestamp_ms),
            "EXN-SIGN-VERSION": "1",
            "EXN-DATA": exn_data,
            "EXN-SIGN": exn_sign,
        }
        if method in ["POST", "PATCH", "PUT"]:
            headers["Content-Type"] = "application/json"

        return headers
