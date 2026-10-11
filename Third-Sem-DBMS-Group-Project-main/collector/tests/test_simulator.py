import random

import pytest

import api_client as ac
import collector
import config
import event_generator as eg
from tests.conftest import (
    SECRET_KEY,
    FakeResponse,
    FakeSession,
    ScriptedClient,
    StepClock,
    auth_failed,
    duplicate,
    rejected,
    stored,
    transient_error,
)


def simulator(client, count=5, interval=2.0, max_errors=10, rate=0.0, lines=None, sleeps=None):
    settings = config.Settings(interval=interval, count=count, max_consecutive_errors=max_errors, duplicate_rate=rate)
    generator = eg.EventGenerator(eg.PROFILES["lab-a"], random.Random(1), StepClock(), rate)
    out = (lines if lines is not None else []).append
    sleep = (sleeps if sleeps is not None else []).append
    return collector.Simulator(client, generator, settings, out=out, sleep=sleep, monotonic=StepClock(step_seconds=1))


def test_sends_exactly_the_requested_number_of_events_and_summarises():
    client = ScriptedClient([stored(), stored(), duplicate(), stored(), duplicate()])
    summary = simulator(client, count=5).run()
    assert len(client.sent) == 5
    assert (summary.sent, summary.stored, summary.duplicate, summary.rejected, summary.errors) == (5, 3, 2, 0, 0)
    assert summary.ok and summary.aborted is None


def test_waits_between_events_but_not_after_the_last_one():
    sleeps = []
    simulator(ScriptedClient([stored()]), count=4, interval=1.5, sleeps=sleeps).run()
    assert sleeps == [1.5, 1.5, 1.5]


def test_each_outcome_is_reported_on_its_own_line():
    lines = []
    simulator(ScriptedClient([stored(11), duplicate(11), rejected("deviceIp: bad")]), count=3, lines=lines).run()
    assert "STORED" in lines[0] and "event 11" in lines[0]
    assert "DUPLICATE" in lines[1] and "repeat of event 11" in lines[1]
    assert "REJECTED" in lines[2] and "422: deviceIp: bad" in lines[2]
    assert all("->" in line and "PC-LAB-A-" in line for line in lines)


def test_intended_repeats_are_marked():
    lines = []
    simulator(ScriptedClient([stored(), duplicate()]), count=30, rate=1.0, lines=lines).run()
    assert any("[intended repeat]" in line for line in lines)


def test_a_rejected_event_is_counted_and_the_run_continues():
    client = ScriptedClient([stored(), rejected(), stored()])
    summary = simulator(client, count=3).run()
    assert (summary.stored, summary.rejected) == (2, 1)
    assert summary.aborted is None
    assert summary.ok is False


def test_an_authentication_failure_stops_the_run_immediately():
    client = ScriptedClient([auth_failed()])
    lines, sleeps = [], []
    summary = simulator(client, count=50, lines=lines, sleeps=sleeps).run()
    assert len(client.sent) == 1 and sleeps == []
    assert "authentication failed (401)" in summary.aborted and not summary.ok
    assert "AUTH FAIL" in lines[0]


def test_transient_errors_back_off_and_then_recover():
    client = ScriptedClient([transient_error(), transient_error(), stored(), stored()])
    lines, sleeps = [], []
    summary = simulator(client, count=4, interval=1.0, lines=lines, sleeps=sleeps).run()
    assert sleeps[:2] == [1.0, 2.0]
    assert (summary.errors, summary.stored, summary.aborted) == (2, 2, None)
    assert "retrying in 1.0s, 1/10" in lines[0]


def test_the_consecutive_error_counter_resets_after_a_success():
    outcomes = [transient_error(), transient_error(), stored(), transient_error(), transient_error(), stored()]
    summary = simulator(ScriptedClient(outcomes), count=6, max_errors=3).run()
    assert summary.aborted is None


def test_too_many_consecutive_errors_end_the_run_cleanly():
    client = ScriptedClient([transient_error()])
    sleeps = []
    summary = simulator(client, count=100, max_errors=3, sleeps=sleeps).run()
    assert summary.errors == 3 and "3 consecutive errors" in summary.aborted
    assert len(client.sent) == 3 and not summary.ok


def test_backoff_is_capped():
    sleeps = []
    simulator(ScriptedClient([transient_error()]), count=100, interval=10, max_errors=12, sleeps=sleeps).run()
    assert max(sleeps) == collector.MAX_BACKOFF_SECONDS


def test_ctrl_c_ends_a_continuous_run_with_a_summary():
    client = ScriptedClient([stored(), stored(), KeyboardInterrupt()])
    summary = simulator(client, count=0).run()
    assert summary.stopped_by_user and summary.sent == 2 and summary.ok


def test_a_continuous_run_keeps_going_past_any_fixed_count():
    client = ScriptedClient([stored()] * 30 + [KeyboardInterrupt()])
    summary = simulator(client, count=0).run()
    assert summary.sent == 30 and summary.stopped_by_user


def test_no_event_ever_carries_a_node_id():
    client = ScriptedClient([stored()])
    simulator(client, count=50, rate=0.3).run()
    assert client.sent and all("nodeId" not in event and "node_id" not in event for event in client.sent)


class RuleClient:
    def __init__(self, broken=False):
        self.stored_times, self.broken = [], broken

    def send_event(self, payload):
        from datetime import datetime

        stamp = datetime.fromisoformat(payload["timestamp"])
        near = [t for t in self.stored_times if abs((stamp - t).total_seconds()) <= 30]
        if near and not self.broken:
            return duplicate(1)
        self.stored_times.append(stamp)
        return stored(len(self.stored_times))


def test_the_dedup_demo_passes_against_a_backend_that_follows_the_rule():
    lines = []
    client = RuleClient()
    assert collector.run_dedup_demo(client, eg.PROFILES["lab-a"], out=lines.append) is True
    assert len(client.stored_times) == 3
    assert any("as specified" in line for line in lines)
    assert sum("MISMATCH" in line for line in lines) == 0


def test_the_dedup_demo_fails_loudly_if_nothing_is_deduplicated():
    lines = []
    assert collector.run_dedup_demo(RuleClient(broken=True), eg.PROFILES["lab-a"], out=lines.append) is False
    assert any("MISMATCH" in line for line in lines) and any("UNEXPECTED" in line for line in lines)


@pytest.fixture
def cli(monkeypatch, capsys):
    monkeypatch.setattr(config, "load_env_file", lambda *a, **k: None)
    monkeypatch.setenv("COLLECTOR_API_KEY", SECRET_KEY)
    for name in ("COLLECTOR_PROFILE", "COLLECTOR_COUNT", "COLLECTOR_INTERVAL", "COLLECTOR_SEED", "COLLECTOR_DUPLICATE_RATE"):
        monkeypatch.delenv(name, raising=False)

    def run(argv, replies=None):
        session = FakeSession(replies)
        original = ac.CollectorClient.__init__

        def init(self, base_url, api_key, timeout=5.0, session_=None):
            original(self, base_url, api_key, timeout, session)

        monkeypatch.setattr(ac.CollectorClient, "__init__", init)
        code = collector.main(argv)
        captured = capsys.readouterr()
        return code, captured.out, captured.err, session

    return run


def test_run_mode_prints_progress_a_summary_and_never_the_key(cli):
    code, out, err, session = cli(["run", "--count", "6", "--interval", "0", "--seed", "1"])
    assert code == 0 and "Summary: 6 sent | 6 stored" in out
    assert len(session.posts) == 6
    assert SECRET_KEY not in out and SECRET_KEY not in err
    assert "API key: configured" in out
    assert all(post["headers"] == {"X-API-Key": SECRET_KEY} for post in session.posts)


def test_default_mode_is_run(cli):
    code, out, _, session = cli(["--count", "2", "--interval", "0"])
    assert code == 0 and len(session.posts) == 2 and "Summary: 2 sent" in out


def test_exit_code_reflects_a_failed_run(cli):
    code, out, _, _ = cli(["run", "--count", "3", "--interval", "0"], [FakeResponse(401, {"detail": "Invalid or missing API key"})])
    assert code == 1 and "Aborted: authentication failed (401)" in out
    assert SECRET_KEY not in out


def test_check_mode_reports_the_backend_and_key(cli):
    code, out, _, session = cli(["check"], [FakeResponse(200, {"status": "ok"}), FakeResponse(422, {"detail": []})])
    assert code == 0 and "Backend: reachable" in out and "API key: accepted" in out
    assert len(session.posts) == 1 and session.posts[0]["json"] == {}


def test_check_mode_fails_when_the_backend_is_down(cli):
    import requests

    code, out, _, _ = cli(["check"], [requests.ConnectionError("down")])
    assert code == 1 and "NOT reachable" in out


def test_configuration_errors_exit_2_without_leaking_the_key(cli, monkeypatch):
    code, out, err, _ = cli(["run", "--duplicate-rate", "7"])
    assert code == 2 and "between 0 and 1" in err and SECRET_KEY not in out + err

    monkeypatch.delenv("COLLECTOR_API_KEY")
    code, out, err, _ = cli(["run"])
    assert code == 2 and "COLLECTOR_API_KEY is not set" in err


def test_the_api_key_cannot_be_passed_on_the_command_line():
    with pytest.raises(SystemExit):
        collector.parse_args(["--api-key", "abc"])
