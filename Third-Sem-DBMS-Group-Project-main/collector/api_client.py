"""HTTP client for the backend's collector API (X-API-Key header).

Never raises on a bad response and never includes the key in output.
"""

from dataclasses import dataclass

import requests

STORED = "STORED"  # 201: event recorded
DUPLICATE = "DUPLICATE"  # 200: same device + destination within 30 seconds, not stored (not an error)
REJECTED = "REJECTED"  # 4xx: the backend refused this event (e.g. invalid data)
AUTH_FAILED = "AUTH_FAILED"  # 401 / 403: bad, revoked or disabled key/node; retrying will not help
ERROR = "ERROR"  # network failure or 5xx: transient, safe to retry
KEY_OK = "KEY_OK"

EVENTS_PATH = "/api/collector/events"


@dataclass(frozen=True)
class SendResult:
    outcome: str
    status_code: int | None
    message: str
    history_id: int | None = None
    duplicate_of: int | None = None


def _describe(body, fallback: str) -> str:
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            field = ".".join(str(p) for p in item.get("loc", []) if p not in ("body", "query"))
            parts.append(f"{field}: {item.get('msg')}" if field else str(item.get("msg")))
        return "; ".join(parts) or fallback
    return fallback


class CollectorClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key = api_key
        self.session = session or requests.Session()

    def _scrub(self, text: str) -> str:
        return text.replace(self._api_key, "***") if self._api_key else text

    def _post(self, payload: dict) -> SendResult:
        try:
            response = self.session.post(
                f"{self.base_url}{EVENTS_PATH}",
                json=payload,
                headers={"X-API-Key": self._api_key},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            return SendResult(ERROR, None, self._scrub(f"cannot reach the backend ({type(error).__name__})"))

        try:
            body = response.json()
        except ValueError:
            body = None
        status = response.status_code

        if status == 201 and isinstance(body, dict):
            return SendResult(STORED, status, "stored", history_id=body.get("history_id"))
        if status == 200 and isinstance(body, dict) and body.get("status") == "DUPLICATE":
            return SendResult(DUPLICATE, status, "duplicate within 30 seconds", duplicate_of=body.get("duplicate_of"))
        if status in (401, 403):
            return SendResult(AUTH_FAILED, status, self._scrub(_describe(body, "not authorised")))
        if status >= 500:
            return SendResult(ERROR, status, self._scrub(_describe(body, "backend error")))
        return SendResult(REJECTED, status, self._scrub(_describe(body, f"unexpected response ({status})")))

    def send_event(self, payload: dict) -> SendResult:
        return self._post(payload)

    def check_health(self) -> bool:
        try:
            return self.session.get(f"{self.base_url}/api/health", timeout=self.timeout).status_code == 200
        except requests.RequestException:
            return False

    def check_api_key(self) -> SendResult:
        """Check the key without storing anything: an empty event gets 422 if the key is valid, 401 if not."""
        result = self._post({})
        if result.outcome == REJECTED and result.status_code == 422:
            return SendResult(KEY_OK, 422, "API key accepted")
        return result
