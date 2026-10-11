import ipaddress
import random
from collections import Counter
from datetime import datetime

import pytest

import event_generator as eg
from tests.conftest import StepClock

CONTRACT_FIELDS = {"deviceIdentifier", "deviceIp", "destinationIp", "domain", "timestamp"}
DOC_RANGES = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def make(profile="lab-a", seed=1, rate=0.15, step=2):
    return eg.EventGenerator(
        eg.PROFILES[profile], random.Random(seed), clock=StepClock(step_seconds=step), duplicate_rate=rate
    )


def test_profiles_match_the_seeded_devices():
    counts = {name: len(profile.devices()) for name, profile in eg.PROFILES.items()}
    assert counts == {"lab-a": 5, "lab-b": 5, "lib-01": 4, "admin-01": 3}
    first = eg.PROFILES["lab-a"].devices()[0]
    assert (first.identifier, first.ip) == ("PC-LAB-A-001", "192.168.10.21")
    last = eg.PROFILES["admin-01"].devices()[-1]
    assert (last.identifier, last.ip) == ("PC-ADMIN-003", "192.168.40.23")


def test_every_event_follows_the_contract_and_never_carries_a_node():
    generator = make()
    for _ in range(200):
        payload = generator.next_event().payload
        assert set(payload) <= CONTRACT_FIELDS
        assert {"deviceIdentifier", "deviceIp", "destinationIp", "timestamp"} <= set(payload)
        assert not {"nodeId", "node_id", "node"} & set(payload)


def test_devices_come_only_from_the_chosen_profile():
    for name, profile in eg.PROFILES.items():
        allowed = {(d.identifier, d.ip) for d in profile.devices()}
        generator = make(name)
        seen = {(e.payload["deviceIdentifier"], e.payload["deviceIp"]) for e in (generator.next_event() for _ in range(300))}
        assert seen <= allowed
        assert len(seen) == len(allowed)


def test_destinations_are_synthetic_documentation_addresses():
    for destination in eg.DESTINATIONS:
        address = ipaddress.ip_address(destination.ip)
        assert any(address in network for network in DOC_RANGES), destination
    generator = make()
    for _ in range(100):
        assert generator.next_event().payload["destinationIp"] in {d.ip for d in eg.DESTINATIONS}


def test_some_destinations_have_no_domain_and_are_sent_without_the_field():
    generator = make(seed=5)
    payloads = [generator.next_event().payload for _ in range(1500)]
    without_domain = [p for p in payloads if "domain" not in p]
    assert without_domain and all(p["destinationIp"] == "192.0.2.77" for p in without_domain)
    assert len(without_domain) < len(payloads) * 0.06


def test_popular_destinations_appear_more_often():
    generator = make(seed=9, rate=0)
    counts = Counter(generator.next_event().payload.get("domain") for _ in range(3000))
    assert counts["google.com"] > counts["reddit.com"] > counts["docs.python.org"]


def test_timestamps_come_from_the_clock_in_iso_seconds():
    generator = make(step=2)
    stamps = [datetime.fromisoformat(generator.next_event().payload["timestamp"]) for _ in range(5)]
    assert stamps == [datetime(2026, 9, 20, 10, 0, s) for s in (0, 2, 4, 6, 8)]
    assert all(s.microsecond == 0 for s in stamps)


def test_the_same_seed_gives_the_same_stream():
    def stream(seed):
        generator = make(seed=seed)
        return [generator.next_event() for _ in range(40)]

    assert stream(3) == stream(3)
    assert stream(3) != stream(4)


def test_no_repeats_when_the_rate_is_zero():
    generator = make(rate=0)
    assert not any(generator.next_event().is_repeat for _ in range(200))


def test_repeats_reuse_a_recent_device_and_destination_pair():
    generator = make(rate=1.0, step=2)
    first = generator.next_event()
    assert first.is_repeat is False
    pairs = {(first.payload["deviceIdentifier"], first.payload["destinationIp"], first.payload.get("domain"))}
    for _ in range(10):
        event = generator.next_event()
        assert event.is_repeat is True
        assert (event.payload["deviceIdentifier"], event.payload["destinationIp"], event.payload.get("domain")) in pairs


def test_repeats_stop_once_the_original_is_too_old():
    generator = make(rate=1.0, step=26)
    assert generator.next_event().is_repeat is False
    assert generator.next_event().is_repeat is False


def test_about_the_requested_share_of_events_are_repeats():
    generator = make(seed=2, rate=0.25, step=1)
    events = [generator.next_event() for _ in range(2000)]
    share = sum(e.is_repeat for e in events) / len(events)
    assert 0.18 < share < 0.32


@pytest.mark.parametrize(
    "change, message",
    [
        ({"nodeId": 2}, "unexpected field"),
        ({"node_id": 2}, "unexpected field"),
        ({"deviceIp": "999.1.1.1"}, "does not appear to be"),
        ({"destinationIp": "nope"}, "does not appear to be"),
        ({"domain": "bad domain!"}, "invalid domain"),
        ({"domain": "a..b"}, "invalid domain"),
        ({"timestamp": "yesterday"}, "Invalid isoformat"),
        ({"deviceIdentifier": ""}, "missing deviceIdentifier"),
    ],
)
def test_local_validation_rejects_bad_events(change, message):
    good = eg.build_payload(eg.PROFILES["lab-a"].devices()[0], eg.DESTINATIONS[0], datetime(2026, 9, 20, 10, 0, 0))
    with pytest.raises(ValueError, match=message):
        eg.validate_event({**good, **change})


def test_build_payload_truncates_fractional_seconds():
    payload = eg.build_payload(
        eg.PROFILES["lab-a"].devices()[0], eg.DESTINATIONS[0], datetime(2026, 9, 20, 10, 0, 0, 987654)
    )
    assert payload["timestamp"] == "2026-09-20T10:00:00"
