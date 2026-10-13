# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional, Set


class ConfirmationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ConfirmationService:
    def __init__(self, ttl_seconds: int = 300, secret: Optional[bytes] = None):
        self.ttl_seconds = ttl_seconds
        self.secret = secret or secrets.token_bytes(32)
        self._consumed: Set[str] = set()

    @staticmethod
    def payload_checksum(action: str, payload: Dict[str, Any]) -> str:
        canonical = json.dumps(
            {"action": action, "payload": payload},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def preview(
        self, action: str, payload: Dict[str, Any], *, impact: Any = None,
        before: Any = None, after: Any = None, warnings: Optional[list] = None,
    ) -> Dict[str, Any]:
        token_id = secrets.token_urlsafe(12)
        expires_at = int(time.time()) + self.ttl_seconds
        body = {
            "id": token_id, "action": action,
            "checksum": self.payload_checksum(action, payload),
            "expires_at": expires_at,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(body, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        signature = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return {
            "action": action, "payload": payload, "impact": impact or {},
            "before": before, "after": after, "warnings": warnings or [],
            "confirmation_token": f"{encoded}.{signature}",
            "expires_at": expires_at,
        }

    def validate(
        self, token: str, action: str, payload: Dict[str, Any], *, consume: bool = True,
    ) -> None:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(
                self.secret, encoded.encode("ascii"), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ConfirmationError("confirmation_invalid", "确认令牌无效")
            padded = encoded + "=" * (-len(encoded) % 4)
            body = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        except ConfirmationError:
            raise
        except Exception as exc:
            raise ConfirmationError("confirmation_invalid", "确认令牌无效") from exc
        if body["id"] in self._consumed:
            raise ConfirmationError("confirmation_replayed", "确认令牌已使用")
        if int(body.get("expires_at", 0)) < int(time.time()):
            raise ConfirmationError("confirmation_expired", "确认令牌已过期")
        if body.get("action") != action or body.get("checksum") != self.payload_checksum(action, payload):
            raise ConfirmationError("confirmation_mismatch", "操作内容已变化，请重新确认")
        if consume:
            self._consumed.add(body["id"])


confirmation_service = ConfirmationService()
