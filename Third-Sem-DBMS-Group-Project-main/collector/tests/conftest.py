import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

import pytest  # noqa: E402

import api_client  # noqa: E402
from api_client import SendResult  # noqa: E402

SECRET_KEY = "nm_test_SUPER_SECRET_key_value_123"


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class FakeSession:
    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.posts = []
        self.gets = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        reply = self.replies.pop(0) if self.replies else FakeResponse(201, {"status": "STORED", "history_id": 1})
        if isinstance(reply, Exception):
            raise reply
        return reply

    def get(self, url, timeout=None):
        self.gets.append(url)
        reply = self.replies.pop(0) if self.replies else FakeResponse(200, {"status": "ok"})
        if isinstance(reply, Exception):
            raise reply
        return reply


class ScriptedClient:
    def __init__(self, results):
        self.results = list(results)
        self.sent = []

    def send_event(self, payload):
        self.sent.append(payload)
        if len(self.results) > 1:
            outcome = self.results.pop(0)
        else:
            outcome = self.results[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def stored(history_id=1):
    return SendResult(api_client.STORED, 201, "stored", history_id=history_id)


def duplicate(of=1):
    return SendResult(api_client.DUPLICATE, 200, "duplicate", duplicate_of=of)


def rejected(message="deviceIp: must be valid"):
    return SendResult(api_client.REJECTED, 422, message)


def auth_failed():
    return SendResult(api_client.AUTH_FAILED, 401, "Invalid or missing API key")


def transient_error():
    return SendResult(api_client.ERROR, None, "cannot reach the backend (ConnectionError)")


class StepClock:
    def __init__(self, start=None, step_seconds=2):
        self.current = start or datetime(2026, 9, 20, 10, 0, 0)
        self.step = timedelta(seconds=step_seconds)

    def __call__(self):
        value = self.current
        self.current += self.step
        return value


@pytest.fixture
def rng():
    return random.Random(1234)
