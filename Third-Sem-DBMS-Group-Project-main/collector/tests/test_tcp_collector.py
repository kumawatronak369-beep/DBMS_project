import ipaddress
import socket
import struct
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

import api_client
import collector
import event_generator
import tcp_collector
from api_client import CollectorClient, SendResult
from tcp_collector import (
    STATE_ESTABLISHED,
    STATE_LISTEN,
    Connection,
    TcpEvent,
    TcpRow,
    TcpRunner,
    TcpTableError,
    domains_by_ip,
    outbound_connections,
    parse_ipv4_table,
    parse_ipv6_table,
    read_tcp_table,
)
from tests.conftest import SECRET_KEY, FakeResponse, FakeSession, ScriptedClient, duplicate, rejected, stored

NOW = datetime(2026, 9, 21, 11, 8, 30, 987654)
LOCAL = "192.168.1.3"
TIME_WAIT = 11


def v4_table(rows):
    raw = struct.pack("<L", len(rows))
    for state, local, local_port, remote, remote_port in rows:
        raw += struct.pack(
            "<5L",
            state,
            int.from_bytes(socket.inet_aton(local), "little"),
            socket.htons(local_port),
            int.from_bytes(socket.inet_aton(remote), "little"),
            socket.htons(remote_port),
        )
    return raw


def v6_table(rows, pid=4321):
    raw = struct.pack("<L", len(rows))
    for state, local, local_port, remote, remote_port in rows:
        raw += struct.pack(
            "<16sLL16sLLLL",
            ipaddress.IPv6Address(local).packed,
            0,
            socket.htons(local_port),
            ipaddress.IPv6Address(remote).packed,
            0,
            socket.htons(remote_port),
            state,
            pid,
        )
    return raw


def row(remote="203.0.113.9", remote_port=443, local_port=50000, local=LOCAL, state=STATE_ESTABLISHED):
    return TcpRow(state, local, local_port, remote, remote_port)


def a(name, ip, ttl=300):
    return {"Name": name, "Type": 1, "Data": ip, "TimeToLive": ttl}


def cname(name, target):
    return {"Name": name, "Type": 5, "Data": target, "TimeToLive": 300}


def settings(**over):
    values = dict(device_id="MY-LAPTOP", device_ip="", interval=2.0, count=0, max_consecutive_errors=3)
    values.update(over)
    return SimpleNamespace(**values)


def make_runner(client, tables, dns=None, include_existing=False, out=None, sleep=None, **over):
    feed = iter(tables)

    def read_tcp():
        item = next(feed)
        if isinstance(item, BaseException):
            raise item
        return item

    def read_cache():
        if isinstance(dns, BaseException):
            raise dns
        return dns if dns is not None else []

    return TcpRunner(
        client,
        settings(**over),
        read_tcp=read_tcp,
        read_cache=read_cache,
        include_existing=include_existing,
        out=(out.append if out is not None else (lambda line: None)),
        sleep=sleep or (lambda seconds: None),
        now=lambda: NOW,
    )


def test_ipv4_rows_give_state_addresses_and_ports():
    raw = v4_table([(STATE_ESTABLISHED, "192.168.1.3", 50123, "203.0.113.9", 443)])
    assert parse_ipv4_table(raw) == [TcpRow(STATE_ESTABLISHED, "192.168.1.3", 50123, "203.0.113.9", 443)]


@pytest.mark.parametrize("port", [1, 53, 80, 443, 8080, 49152, 56188, 65535])
def test_ports_are_read_from_network_byte_order(port):
    parsed = parse_ipv4_table(v4_table([(STATE_ESTABLISHED, LOCAL, port, "203.0.113.9", port)]))[0]
    assert (parsed.local_port, parsed.remote_port) == (port, port)


def test_address_bytes_are_read_in_the_right_order():
    parsed = parse_ipv4_table(v4_table([(STATE_ESTABLISHED, "10.1.2.3", 1000, "198.51.100.200", 2000)]))[0]
    assert (parsed.local_ip, parsed.remote_ip) == ("10.1.2.3", "198.51.100.200")


def test_several_rows_keep_their_order():
    rows = parse_ipv4_table(v4_table([(STATE_LISTEN, "0.0.0.0", 135, "0.0.0.0", 0), (STATE_ESTABLISHED, LOCAL, 50000, "203.0.113.9", 443)]))
    assert [r.state for r in rows] == [STATE_LISTEN, STATE_ESTABLISHED]
    assert rows[0].local_port == 135 and rows[1].remote_port == 443


def test_ipv6_rows_are_parsed_and_the_process_id_is_discarded():
    raw = v6_table([(STATE_ESTABLISHED, "2001:db8::10", 51000, "2001:db8:1::443", 443)], pid=999)
    (parsed,) = parse_ipv6_table(raw)
    assert (parsed.local_ip, parsed.local_port, parsed.remote_ip, parsed.remote_port) == ("2001:db8::10", 51000, "2001:db8:1::443", 443)
    assert "999" not in repr(parsed)
    assert {"pid", "process", "owning_pid"}.isdisjoint(TcpRow.__dataclass_fields__)


def test_only_tcp_is_ever_reported():
    connection = next(iter(outbound_connections([row()])))
    event = TcpEvent(connection, None)
    runner = make_runner(ScriptedClient([stored()]), [[]])
    assert runner._payload(event, NOW)["protocol"] == "TCP"


def test_empty_and_truncated_tables_are_handled():
    assert parse_ipv4_table(b"") == [] and parse_ipv6_table(b"\x00") == []
    assert parse_ipv4_table(struct.pack("<L", 0)) == []
    good = v4_table([(STATE_ESTABLISHED, LOCAL, 50000, "203.0.113.9", 443), (STATE_ESTABLISHED, LOCAL, 50001, "203.0.113.10", 443)])
    assert len(parse_ipv4_table(good[:-5])) == 1
    lying = struct.pack("<L", 1_000_000) + good[4:]
    assert len(parse_ipv4_table(lying)) == 2


def test_reading_combines_ipv4_and_ipv6_and_asks_for_the_table_without_processes_for_ipv4(monkeypatch):
    monkeypatch.setattr(tcp_collector.sys, "platform", "win32")
    calls = []

    def fetch(family, table_class):
        calls.append((family, table_class))
        if family == tcp_collector.AF_INET:
            return v4_table([(STATE_ESTABLISHED, LOCAL, 50000, "203.0.113.9", 443)])
        return v6_table([(STATE_ESTABLISHED, "2001:db8::10", 51000, "2001:db8:1::443", 443)])

    rows = read_tcp_table(fetch)
    assert [r.remote_ip for r in rows] == ["203.0.113.9", "2001:db8:1::443"]
    assert calls[0] == (tcp_collector.AF_INET, tcp_collector.TCP_TABLE_BASIC_ALL)
    assert calls[1] == (tcp_collector.AF_INET6, tcp_collector.TCP_TABLE_OWNER_PID_ALL)


def test_missing_ipv6_is_not_fatal_but_missing_ipv4_is(monkeypatch):
    monkeypatch.setattr(tcp_collector.sys, "platform", "win32")

    def no_ipv6(family, table_class):
        if family == tcp_collector.AF_INET6:
            raise TcpTableError("IPv6 disabled")
        return v4_table([(STATE_ESTABLISHED, LOCAL, 50000, "203.0.113.9", 443)])

    assert len(read_tcp_table(no_ipv6)) == 1

    def no_ipv4(family, table_class):
        raise TcpTableError("boom")

    with pytest.raises(TcpTableError):
        read_tcp_table(no_ipv4)


def test_it_refuses_to_run_off_windows(monkeypatch):
    monkeypatch.setattr(tcp_collector.sys, "platform", "linux")
    with pytest.raises(TcpTableError, match="Windows only"):
        read_tcp_table(lambda family, table_class: b"")


@pytest.mark.skipif(sys.platform != "win32", reason="reads the real Windows table")
def test_the_real_windows_call_works_without_elevation_and_yields_valid_rows():
    rows = read_tcp_table()
    assert isinstance(rows, list)
    for r in rows:
        assert 0 <= r.local_port <= 65535 and 0 <= r.remote_port <= 65535
        ipaddress.ip_address(r.local_ip)
        ipaddress.ip_address(r.remote_ip)


def test_only_established_connections_are_reported():
    rows = [
        row(remote="203.0.113.9", local_port=50000, state=STATE_ESTABLISHED),
        row(remote="203.0.113.10", local_port=50001, state=STATE_LISTEN),
        row(remote="203.0.113.11", local_port=50002, state=TIME_WAIT),
        row(remote="203.0.113.12", local_port=50003, state=1),
        row(remote="203.0.113.13", local_port=50004, state=3),
    ]
    assert {c.remote_ip for c in outbound_connections(rows)} == {"203.0.113.9"}


def test_connections_to_a_listening_local_port_are_inbound_and_skipped():
    rows = [
        TcpRow(STATE_LISTEN, "0.0.0.0", 8000, "0.0.0.0", 0),
        TcpRow(STATE_ESTABLISHED, LOCAL, 8000, "198.51.100.7", 61000),
        row(remote="203.0.113.9", local_port=50000),
    ]
    assert {c.remote_ip for c in outbound_connections(rows)} == {"203.0.113.9"}


@pytest.mark.parametrize("remote", ["127.0.0.1", "127.8.9.10", "0.0.0.0", "169.254.7.7", "224.0.0.251", "::1", "::", "fe80::1", "ff02::1", LOCAL])
def test_local_and_unroutable_remotes_are_skipped(remote):
    assert outbound_connections([row(remote=remote)]) == set()


@pytest.mark.parametrize("remote", ["203.0.113.9", "198.51.100.7", "192.168.1.1", "10.0.0.5", "2001:db8::443"])
def test_ordinary_and_lan_remotes_are_reported(remote):
    assert {c.remote_ip for c in outbound_connections([row(remote=remote)])} == {remote}


def test_a_connection_carries_exactly_the_four_windows_values():
    (connection,) = outbound_connections([row(remote="203.0.113.9", remote_port=443, local_port=56188)])
    assert connection == Connection(LOCAL, 56188, "203.0.113.9", 443)
    assert set(Connection.__dataclass_fields__) == {"local_ip", "local_port", "remote_ip", "remote_port"}


def test_ipv6_connections_are_reported_with_compressed_addresses():
    (connection,) = outbound_connections([TcpRow(STATE_ESTABLISHED, "2001:db8:0:0:0:0:0:10", 51000, "2001:db8:1::443", 443)])
    assert (connection.local_ip, connection.remote_ip) == ("2001:db8::10", "2001:db8:1::443")


def test_identical_rows_are_one_connection():
    assert len(outbound_connections([row(), row()])) == 1


@pytest.mark.parametrize(
    "bad",
    [
        TcpRow(STATE_ESTABLISHED, LOCAL, 0, "203.0.113.9", 443),
        TcpRow(STATE_ESTABLISHED, LOCAL, 50000, "203.0.113.9", 0),
        TcpRow(STATE_ESTABLISHED, LOCAL, 70000, "203.0.113.9", 443),
        TcpRow(STATE_ESTABLISHED, LOCAL, 50000, "not-an-ip", 443),
        TcpRow(STATE_ESTABLISHED, "not-an-ip", 50000, "203.0.113.9", 443),
        TcpRow(STATE_ESTABLISHED, None, 50000, "203.0.113.9", 443),
        TcpRow(STATE_ESTABLISHED, LOCAL, "x", "203.0.113.9", 443),
    ],
)
def test_a_malformed_row_is_skipped_without_affecting_the_rest(bad):
    good = row(remote="198.51.100.7")
    assert {c.remote_ip for c in outbound_connections([bad, good])} == {"198.51.100.7"}


def test_a_domain_is_used_when_exactly_one_cached_name_maps_to_the_ip():
    assert domains_by_ip([a("example.org", "203.0.113.9")]) == {"203.0.113.9": "example.org"}


def test_a_shared_ip_gets_no_domain_instead_of_an_arbitrary_one():
    rows = [a("one.example.org", "203.0.113.9"), a("two.example.org", "203.0.113.9"), a("solo.example.org", "203.0.113.10")]
    assert domains_by_ip(rows) == {"203.0.113.9": None, "203.0.113.10": "solo.example.org"}


def test_an_alias_chain_gives_the_name_that_was_asked_for():
    rows = [cname("login.example.org", "edge.cdn.example.net"), a("edge.cdn.example.net", "203.0.113.9")]
    assert domains_by_ip(rows) == {"203.0.113.9": "login.example.org"}


def test_ips_absent_from_the_cache_are_unknown_and_there_is_no_reverse_lookup(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no reverse DNS lookup may ever be made")

    monkeypatch.setattr(socket, "gethostbyaddr", forbidden)
    monkeypatch.setattr(socket, "getnameinfo", forbidden)
    assert domains_by_ip([]) == {}
    assert domains_by_ip([a("example.org", "203.0.113.9")]).get("203.0.113.77") is None
    runner = make_runner(ScriptedClient([stored()]), [[], [row(remote="203.0.113.77")]], dns=[a("example.org", "203.0.113.9")])
    runner.step(), runner.step()


def test_a_new_connection_is_sent_with_exactly_the_observed_values():
    client = ScriptedClient([stored(41)])
    runner = make_runner(client, [[], [row(remote="203.0.113.9", remote_port=443, local_port=56188)]], dns=[a("example.org", "203.0.113.9")])
    assert runner.step() and runner.step()
    assert client.sent == [
        {
            "deviceIdentifier": "MY-LAPTOP",
            "deviceIp": LOCAL,
            "destinationIp": "203.0.113.9",
            "domain": "example.org",
            "timestamp": "2026-09-21T11:08:30",
            "protocol": "TCP",
            "sourcePort": 56188,
            "destinationPort": 443,
        }
    ]
    assert runner.summary.stored == 1 and runner.summary.sent == 1


def test_the_timestamp_is_the_observation_time_without_fractions_or_zone():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()]])
    runner.step(), runner.step()
    assert client.sent[0]["timestamp"] == "2026-09-21T11:08:30"


def test_no_node_id_and_no_extra_fields_are_ever_sent():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()]])
    runner.step(), runner.step()
    assert set(client.sent[0]) <= {"deviceIdentifier", "deviceIp", "destinationIp", "domain", "timestamp", "protocol", "sourcePort", "destinationPort"}
    assert "nodeId" not in client.sent[0]


def test_the_domain_is_null_when_it_cannot_be_determined():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row(remote="203.0.113.9")]], dns=[])
    runner.step(), runner.step()
    assert client.sent[0]["domain"] is None


def test_a_shared_ip_is_sent_with_a_null_domain():
    client = ScriptedClient([stored()])
    dns = [a("one.example.org", "203.0.113.9"), a("two.example.org", "203.0.113.9")]
    runner = make_runner(client, [[], [row(remote="203.0.113.9")]], dns=dns)
    runner.step(), runner.step()
    assert client.sent[0]["domain"] is None


def test_the_device_ip_is_the_connections_own_local_address_not_a_configured_one():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row(local="10.9.8.7")]], device_ip="192.0.2.99")
    runner.step(), runner.step()
    assert client.sent[0]["deviceIp"] == "10.9.8.7"


def test_the_device_identifier_is_configured_and_not_the_ip(monkeypatch):
    assert make_runner(ScriptedClient([stored()]), [[]], device_id="LIVING-ROOM-PC").device_id == "LIVING-ROOM-PC"
    monkeypatch.setattr(tcp_collector.socket, "gethostname", lambda: "my host")
    fallback = make_runner(ScriptedClient([stored()]), [[]], device_id="")
    assert fallback.device_id == "MY-HOST" and "." not in fallback.device_id


def test_the_first_look_is_only_a_starting_point_by_default():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[row()], [row()]])
    runner.step(), runner.step()
    assert client.sent == []


def test_existing_connections_can_be_reported_on_request():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[row(remote="203.0.113.9"), row(remote="203.0.113.10")], []], include_existing=True)
    runner.step()
    assert [p["destinationIp"] for p in client.sent] == ["203.0.113.9", "203.0.113.10"]


def test_a_connection_that_stays_open_is_sent_once_not_every_poll():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()], [row()], [row()], [row()]])
    for _ in range(5):
        runner.step()
    assert len(client.sent) == 1


def test_a_second_connection_is_a_new_event_while_the_first_stays_quiet():
    client = ScriptedClient([stored()])
    first, second = row(remote="203.0.113.9", local_port=50000), row(remote="203.0.113.9", local_port=50001)
    runner = make_runner(client, [[], [first], [first, second]])
    for _ in range(3):
        runner.step()
    assert [p["sourcePort"] for p in client.sent] == [50000, 50001]


def test_a_connection_that_closed_and_later_reappears_counts_as_new():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()], [], [row()]])
    for _ in range(4):
        runner.step()
    assert len(client.sent) == 2


def test_new_connections_in_one_look_are_sent_in_a_stable_order():
    client = ScriptedClient([stored()])
    rows = [row(remote="203.0.113.30", local_port=50002), row(remote="203.0.113.10", local_port=50001), row(remote="203.0.113.20", local_port=50000)]
    make_runner(client, [[], rows]).step()
    runner = make_runner(client, [[], rows])
    runner.step(), runner.step()
    assert [p["destinationIp"] for p in client.sent[-3:]] == ["203.0.113.10", "203.0.113.20", "203.0.113.30"]


def test_the_dns_cache_is_only_read_when_there_is_something_new():
    reads = []
    feed = iter([[], [row()], [row()]])
    runner = TcpRunner(
        ScriptedClient([stored()]),
        settings(),
        read_tcp=lambda: next(feed),
        read_cache=lambda: reads.append(1) or [],
        out=lambda line: None,
        sleep=lambda s: None,
        now=lambda: NOW,
    )
    for _ in range(3):
        runner.step()
    assert len(reads) == 1


def test_the_backend_rule_stays_authoritative_a_duplicate_answer_is_not_an_error():
    client = ScriptedClient([duplicate(7)])
    runner = make_runner(client, [[], [row()]])
    runner.step(), runner.step()
    assert (runner.summary.duplicate, runner.summary.errors, runner.summary.aborted) == (1, 0, None)


def test_events_are_never_changed_after_sending_even_if_dns_arrives_later():
    client = ScriptedClient([stored()])
    feed_dns = [[], [a("example.org", "203.0.113.9")]]
    tables = iter([[], [row(remote="203.0.113.9", local_port=50000)], [row(remote="203.0.113.9", local_port=50000), row(remote="203.0.113.9", local_port=50001)]])
    cache = iter(feed_dns)
    runner = TcpRunner(client, settings(), read_tcp=lambda: next(tables), read_cache=lambda: next(cache), out=lambda line: None, sleep=lambda s: None, now=lambda: NOW)
    for _ in range(3):
        runner.step()
    assert [p["domain"] for p in client.sent] == [None, "example.org"]
    assert len(client.sent) == 2


def test_events_are_still_sent_with_a_null_domain_when_the_dns_cache_fails():
    from local_collector import LocalCollectorError

    lines = []
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()], [row(remote="203.0.113.10", local_port=50002)]], dns=LocalCollectorError("no PowerShell"), out=lines)
    for _ in range(3):
        assert runner.step()
    assert [p["domain"] for p in client.sent] == [None, None]
    assert sum("DNS cache unavailable" in line for line in lines) == 1


def test_an_unexpected_dns_problem_never_stops_the_collector():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], [row()]], dns=ValueError("garbled"))
    assert runner.step() and runner.step()
    assert len(client.sent) == 1


def test_a_temporary_table_failure_is_tolerated_and_the_run_carries_on():
    lines = []
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[], TcpTableError("busy"), [row()]], out=lines)
    assert [runner.step(), runner.step(), runner.step()] == [True, True, True]
    assert len(client.sent) == 1
    assert any("Could not read the TCP connection table: busy" in line for line in lines)


def test_repeated_table_failures_eventually_end_the_run_cleanly():
    runner = make_runner(ScriptedClient([stored()]), [TcpTableError("gone")] * 5, max_consecutive_errors=3)
    summary = runner.run()
    assert summary.aborted == "gone" and not summary.stopped_by_user


def test_a_table_failure_still_delivers_queued_events():
    down = SendResult(api_client.ERROR, None, "connection refused")
    client = ScriptedClient([down, stored()])
    runner = make_runner(client, [[], [row()], TcpTableError("busy")])
    runner.step(), runner.step()
    assert len(runner.pending) == 1
    runner.step()
    assert len(runner.pending) == 0 and runner.summary.stored == 1


def test_a_malformed_row_in_a_real_looking_table_does_not_lose_the_good_ones():
    client = ScriptedClient([stored()])
    bad = TcpRow(STATE_ESTABLISHED, LOCAL, 50000, "garbage", 443)
    runner = make_runner(client, [[], [bad, row(remote="198.51.100.7")]])
    runner.step(), runner.step()
    assert [p["destinationIp"] for p in client.sent] == ["198.51.100.7"]


def test_an_event_that_fails_local_validation_is_skipped_and_the_next_is_still_sent():
    lines = []
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[]], out=lines)
    runner.pending.append((TcpEvent(Connection("not-an-ip", 50000, "203.0.113.9", 443), None), NOW))
    runner.pending.append((TcpEvent(Connection(LOCAL, 50001, "203.0.113.10", 443), None), NOW))
    assert runner.step() is True
    assert runner.summary.skipped == 1 and runner.summary.stored == 1
    assert [p["destinationIp"] for p in client.sent] == ["203.0.113.10"]
    assert "1 skipped" in runner.summary.line()
    assert any("SKIPPED" in line for line in lines)


def test_events_go_through_the_existing_collector_api_with_the_api_key_header():
    session = FakeSession([FakeResponse(200, {"status": "ok"}), FakeResponse(201, {"status": "STORED", "history_id": 77})])
    client = CollectorClient("http://backend.test", SECRET_KEY, session=session)
    runner = make_runner(client, [[], [row(remote="203.0.113.9", remote_port=443, local_port=56188)]])
    runner.step()
    session.replies = [FakeResponse(201, {"status": "STORED", "history_id": 77})]
    runner.step()
    (post,) = session.posts
    assert post["url"] == "http://backend.test" + api_client.EVENTS_PATH
    assert post["headers"]["X-API-Key"] == SECRET_KEY
    assert post["json"]["protocol"] == "TCP" and post["json"]["destinationPort"] == 443 and post["json"]["sourcePort"] == 56188


def test_the_api_key_is_never_printed():
    lines = []
    session = FakeSession([FakeResponse(201, {"status": "STORED", "history_id": 1})])
    runner = make_runner(CollectorClient("http://backend.test", SECRET_KEY, session=session), [[], [row()]], out=lines)
    runner.step(), runner.step()
    assert lines and all(SECRET_KEY not in line and "nm_" not in line for line in lines)


def test_a_refused_key_stops_the_run_at_once():
    client = ScriptedClient([SendResult(api_client.AUTH_FAILED, 401, "Invalid or missing API key")])
    runner = make_runner(client, [[], [row(remote="203.0.113.9")], [row(remote="203.0.113.9"), row(remote="203.0.113.10")]])
    summary = runner.run()
    assert summary.aborted and "API key" in summary.aborted
    assert len(client.sent) == 1


def test_a_disabled_node_is_treated_like_a_refused_key():
    client = ScriptedClient([SendResult(api_client.AUTH_FAILED, 403, "This node is disabled")])
    runner = make_runner(client, [[], [row()], [row()]])
    assert runner.run().aborted


def test_a_backend_that_is_down_keeps_events_queued_and_retries_with_the_original_time():
    down = SendResult(api_client.ERROR, None, "connection refused")
    client = ScriptedClient([down, down, stored(9)])
    times = iter([datetime(2026, 9, 21, 11, 0, 0), datetime(2026, 9, 21, 11, 5, 0), datetime(2026, 9, 21, 11, 6, 0)])
    feed = iter([[], [row()], [row()], [row()]])
    runner = TcpRunner(client, settings(max_consecutive_errors=5), read_tcp=lambda: next(feed), read_cache=lambda: [], out=lambda line: None, sleep=lambda s: None, now=lambda: next(times))
    for _ in range(4):
        runner.step()
    assert runner.summary.stored == 1 and not runner.pending
    assert {p["timestamp"] for p in client.sent} == {"2026-09-21T11:00:00"}


def test_the_wait_grows_while_the_backend_is_failing_and_resets_after_it_recovers():
    runner = make_runner(ScriptedClient([stored()]), [[]], interval=2.0)
    assert runner._delay() == 2.0
    waits = []
    for errors in range(1, 8):
        runner.summary.errors = errors
        waits.append(runner._delay())
    assert waits == sorted(waits) and waits[0] > 2.0 and max(waits) <= 30
    runner.summary.errors = 0
    assert runner._delay() == 2.0


def test_too_many_consecutive_backend_errors_end_the_run():
    down = SendResult(api_client.ERROR, None, "connection refused")
    runner = make_runner(ScriptedClient([down]), [[], [row()]] + [[row()]] * 6, max_consecutive_errors=3)
    summary = runner.run()
    assert summary.aborted and "errors" in summary.aborted


def test_a_rejected_event_is_counted_and_the_run_continues():
    client = ScriptedClient([rejected("destinationPort: bad"), stored()])
    runner = make_runner(client, [[], [row(remote="203.0.113.9"), row(remote="203.0.113.10")]])
    runner.step(), runner.step()
    assert (runner.summary.rejected, runner.summary.stored, runner.summary.aborted) == (1, 1, None)


def test_ctrl_c_while_reading_the_table_stops_cleanly():
    runner = make_runner(ScriptedClient([stored()]), [KeyboardInterrupt()])
    summary = runner.run()
    assert summary.stopped_by_user and summary.aborted is None and summary.ok


def test_ctrl_c_while_waiting_between_looks_stops_cleanly():
    def interrupted(seconds):
        raise KeyboardInterrupt

    runner = make_runner(ScriptedClient([stored()]), [[], [row()]], sleep=interrupted)
    summary = runner.run()
    assert summary.stopped_by_user and summary.ok


def test_the_run_waits_the_interval_between_looks_and_honours_the_event_limit():
    waits = []
    client = ScriptedClient([stored()])
    tables = [[], [row(remote="203.0.113.9")], [row(remote="203.0.113.9"), row(remote="203.0.113.10")], [row(remote="203.0.113.9"), row(remote="203.0.113.10"), row(remote="203.0.113.11")]]
    runner = make_runner(client, tables, count=2, interval=2.0, sleep=waits.append)
    summary = runner.run()
    assert summary.sent == 2 and waits and set(waits) == {2.0}


def test_the_event_contract_accepts_connection_metadata_and_rejects_invalid_values():
    good = {"deviceIdentifier": "PC", "deviceIp": LOCAL, "destinationIp": "203.0.113.9", "timestamp": "2026-09-21T11:08:30", "domain": None, "protocol": "TCP", "sourcePort": 1, "destinationPort": 65535}
    assert event_generator.validate_event(dict(good)) == good
    for change in ({"protocol": "ICMP"}, {"sourcePort": 0}, {"destinationPort": 65536}, {"sourcePort": "443"}, {"sourcePort": True}, {"nodeId": 3}):
        with pytest.raises(ValueError):
            event_generator.validate_event({**good, **change})
    with pytest.raises(ValueError, match="protocol is required"):
        event_generator.validate_event({k: v for k, v in good.items() if k != "protocol"})


def test_simulator_events_still_validate_and_carry_no_connection_metadata():
    generator = event_generator.EventGenerator(event_generator.PROFILES["lab-a"], __import__("random").Random(1), duplicate_rate=0)
    payload = generator.next_event().payload
    assert not {"protocol", "sourcePort", "destinationPort"} & set(payload)


def test_the_command_line_has_local_and_keeps_every_existing_mode():
    for mode in ("run", "check", "demo-dedup", "local", "local-dns"):
        assert collector.parse_args([mode]).mode == mode
    assert collector.parse_args([]).mode == "run"
    assert collector.parse_args(["local", "--include-existing"]).include_existing is True
    assert collector.parse_args(["local"]).include_existing is False


def test_local_mode_needs_an_api_key_but_no_profile(monkeypatch, capsys):
    for name in ("COLLECTOR_API_KEY", "COLLECTOR_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(collector.config, "ENV_FILE", collector.config.ENV_FILE.with_name("does-not-exist.env"))
    assert collector.main(["local"]) == 2
    assert "COLLECTOR_API_KEY is not set" in capsys.readouterr().err


def test_local_mode_says_what_it_watches_and_that_it_is_this_computer_only(monkeypatch, capsys):
    session = FakeSession([FakeResponse(200, {"status": "ok"}), FakeResponse(422, {"detail": []})])
    client = CollectorClient("http://backend.test", SECRET_KEY, session=session)
    monkeypatch.setattr(tcp_collector, "read_tcp_table", lambda: [])

    class InstantRunner(tcp_collector.TcpRunner):
        def run(self):
            summary = self.summary
            summary.stopped_by_user = True
            return summary

    monkeypatch.setattr(tcp_collector, "TcpRunner", InstantRunner)
    cfg = settings(backend_url="http://backend.test")
    assert collector.run_local_tcp(client, cfg) == 0
    text = capsys.readouterr().out
    assert "Local collector -> http://backend.test" in text
    assert "Device: MY-LAPTOP" in text
    assert "Watching local TCP connections of this computer" in text and "no other devices" in text
    assert "Press Ctrl+C to stop." in text
    assert SECRET_KEY not in text
    assert "whole network" not in text.lower() and "entire network" not in text.lower()


def test_local_mode_fails_fast_with_a_clear_message_if_the_table_is_unreadable(monkeypatch, capsys):
    session = FakeSession([FakeResponse(200, {"status": "ok"}), FakeResponse(422, {"detail": []})])
    client = CollectorClient("http://backend.test", SECRET_KEY, session=session)

    def unreadable():
        raise TcpTableError("the local TCP collector reads the Windows TCP table, so it runs on Windows only")

    monkeypatch.setattr(tcp_collector, "read_tcp_table", unreadable)
    assert collector.run_local_tcp(client, settings(backend_url="http://backend.test")) == 1
    assert "Cannot start" in capsys.readouterr().err
