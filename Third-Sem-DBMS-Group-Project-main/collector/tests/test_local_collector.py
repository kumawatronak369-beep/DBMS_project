import json
import subprocess
from datetime import datetime
from types import SimpleNamespace

import pytest

import api_client
import local_collector
from api_client import SendResult
from local_collector import DnsWatcher, LocalCollectorError, LocalRunner, Lookup, extract_lookups
from tests.conftest import ScriptedClient, duplicate, rejected, stored

NOW = datetime(2026, 9, 20, 11, 8, 30, 123456)


def a(name, ip, ttl=300):
    return {"Name": name, "Type": 1, "Data": ip, "TimeToLive": ttl}


def cname(name, target, ttl=300):
    return {"Name": name, "Type": 5, "Data": target, "TimeToLive": ttl}


def settings(**over):
    values = dict(device_id="MY-LAPTOP", device_ip="192.168.1.3", interval=0, count=0, max_consecutive_errors=3)
    values.update(over)
    return SimpleNamespace(**values)


def fake_run(stdout="", returncode=0):
    return lambda *a, **k: subprocess.CompletedProcess(a, returncode, stdout=stdout, stderr="")


def test_reads_a_list_and_a_single_entry(monkeypatch):
    monkeypatch.setattr(local_collector.sys, "platform", "win32")
    rows = [a("github.com", "20.207.73.82")]
    assert local_collector.read_dns_cache(fake_run(json.dumps(rows))) == rows
    assert local_collector.read_dns_cache(fake_run(json.dumps(rows[0]))) == rows
    assert local_collector.read_dns_cache(fake_run("")) == []


def test_cache_read_failures_are_reported_not_raised_raw(monkeypatch):
    monkeypatch.setattr(local_collector.sys, "platform", "win32")
    with pytest.raises(LocalCollectorError):
        local_collector.read_dns_cache(fake_run("", returncode=1))
    with pytest.raises(LocalCollectorError):
        local_collector.read_dns_cache(fake_run("not json"))

    def missing(*args, **kwargs):
        raise FileNotFoundError

    with pytest.raises(LocalCollectorError):
        local_collector.read_dns_cache(missing)


def test_it_refuses_to_run_off_windows(monkeypatch):
    monkeypatch.setattr(local_collector.sys, "platform", "linux")
    with pytest.raises(LocalCollectorError, match="Windows"):
        local_collector.read_dns_cache(fake_run("[]"))


def test_address_records_become_domain_and_ip_pairs():
    result = extract_lookups([a("GitHub.com.", "20.207.73.82", 38), a("github.com", "2606:50c0:8000::154", 40)])
    assert result == {("github.com", "20.207.73.82"): 38, ("github.com", "2606:50c0:8000::154"): 40}


def test_an_alias_chain_is_followed_back_to_the_name_that_was_asked_for():
    rows = [
        cname("login.live.com", "login.msa.msidentity.com"),
        cname("login.msa.msidentity.com", "www.tm.lg.prod.aadmsa.akadns.net"),
        a("www.tm.lg.prod.aadmsa.akadns.net", "40.126.31.71"),
    ]
    assert list(extract_lookups(rows)) == [("login.live.com", "40.126.31.71")]


def test_two_names_pointing_at_the_same_target_are_both_reported():
    rows = [cname("one.example.org", "cdn.example.net"), cname("two.example.org", "cdn.example.net"), a("cdn.example.net", "203.0.113.9")]
    assert {domain for domain, _ in extract_lookups(rows)} == {"one.example.org", "two.example.org"}


def test_an_alias_loop_does_not_hang():
    rows = [cname("a.example.org", "b.example.org"), cname("b.example.org", "a.example.org"), a("a.example.org", "203.0.113.9")]
    extract_lookups(rows)


@pytest.mark.parametrize(
    "row",
    [
        a("printer.local", "192.168.1.50"),
        a("mypc", "192.168.1.3"),
        a("wpad.example.org", "203.0.113.9"),
        a("1.1.168.192.in-addr.arpa", "203.0.113.9"),
        a("blocked.example.org", "0.0.0.0"),
        a("localhost.example.org", "127.0.0.1"),
        a("v6.example.org", "::1"),
        a("bad name.example.org", "203.0.113.9"),
        a("x" * 70 + ".example.org", "203.0.113.9"),
        a("example.org", "not-an-ip"),
        {"Name": "text.example.org", "Type": 16, "Data": "v=spf1", "TimeToLive": 10},
        {"Name": "", "Type": 1, "Data": "203.0.113.9"},
    ],
)
def test_names_and_answers_that_are_not_destinations_are_skipped(row):
    assert extract_lookups([row]) == {}


def test_the_first_look_is_only_the_starting_point():
    watcher = DnsWatcher()
    assert watcher.poll({("github.com", "1.1.1.1"): 200}) == []


def test_only_newly_appearing_names_are_returned():
    watcher = DnsWatcher()
    watcher.poll({("github.com", "1.1.1.1"): 200})
    new = watcher.poll({("github.com", "1.1.1.1"): 198, ("python.org", "2.2.2.2"): 300})
    assert new == [Lookup("python.org", "2.2.2.2", 300)]
    assert watcher.poll({("github.com", "1.1.1.1"): 196, ("python.org", "2.2.2.2"): 298}) == []


def test_a_name_that_expired_and_was_looked_up_again_counts_again():
    watcher = DnsWatcher()
    watcher.poll({("github.com", "1.1.1.1"): 5})
    assert watcher.poll({}) == []
    assert watcher.poll({("github.com", "1.1.1.1"): 300}) == [Lookup("github.com", "1.1.1.1", 300)]


def test_a_refreshed_ttl_counts_as_a_new_lookup_but_normal_ticking_does_not():
    watcher = DnsWatcher()
    watcher.poll({("github.com", "1.1.1.1"): 50})
    assert watcher.poll({("github.com", "1.1.1.1"): 48}) == []
    assert watcher.poll({("github.com", "1.1.1.1"): 300}) == [Lookup("github.com", "1.1.1.1", 300)]


def test_the_same_site_on_a_new_address_is_a_new_lookup():
    watcher = DnsWatcher()
    watcher.poll({("github.com", "1.1.1.1"): 100})
    assert watcher.poll({("github.com", "1.1.1.1"): 98, ("github.com", "9.9.9.9"): 300}) == [Lookup("github.com", "9.9.9.9", 300)]


def test_one_visit_answered_with_ipv4_and_ipv6_is_reported_once_preferring_ipv4():
    watcher = DnsWatcher()
    watcher.poll({})
    new = watcher.poll({("wikipedia.org", "2620:0:861:ed1a::1"): 300, ("wikipedia.org", "208.80.154.224"): 300})
    assert new == [Lookup("wikipedia.org", "208.80.154.224", 300)]
    assert watcher.poll({("wikipedia.org", "2620:0:861:ed1a::1"): 298, ("wikipedia.org", "208.80.154.224"): 298}) == []


def test_a_site_with_only_an_ipv6_answer_is_still_reported():
    watcher = DnsWatcher()
    watcher.poll({})
    assert watcher.poll({("v6only.example.org", "2001:db8::1"): 60}) == [Lookup("v6only.example.org", "2001:db8::1", 60)]


def test_device_identifier_is_a_clean_uppercase_host_name():
    assert local_collector.device_identifier("My Laptop_01") == "MY-LAPTOP_01"
    assert local_collector.device_identifier("é") == "-"
    assert len(local_collector.device_identifier("x" * 300)) == 100


def test_local_ip_is_a_valid_address():
    import ipaddress

    ipaddress.ip_address(local_collector.local_ip())


def make_runner(client, caches, **over):
    feed = iter(caches)
    return LocalRunner(client, settings(**over), read_cache=lambda: next(feed), out=lambda line: None, sleep=lambda s: None, now=lambda: NOW)


def test_new_sites_are_sent_as_metadata_only_with_the_local_device():
    client = ScriptedClient([stored(11)])
    runner = make_runner(client, [[a("github.com", "20.207.73.82")], [a("github.com", "20.207.73.82"), a("python.org", "151.101.0.223")]], count=1)
    summary = runner.run()
    assert client.sent == [
        {
            "deviceIdentifier": "MY-LAPTOP",
            "deviceIp": "192.168.1.3",
            "destinationIp": "151.101.0.223",
            "domain": "python.org",
            "timestamp": "2026-09-20T11:08:30",
        }
    ]
    assert "nodeId" not in client.sent[0]
    assert (summary.sent, summary.stored, summary.ok) == (1, 1, True)


def test_the_starting_cache_is_not_reported():
    client = ScriptedClient([stored()])
    runner = make_runner(client, [[a("github.com", "20.207.73.82")], [a("github.com", "20.207.73.82")]])
    runner.step()
    runner.step()
    assert client.sent == []


def test_duplicates_and_rejections_are_counted_and_the_run_goes_on():
    client = ScriptedClient([duplicate(5), rejected(), stored()])
    runner = make_runner(client, [[], [a("a.example.org", "203.0.113.1"), a("b.example.org", "203.0.113.2"), a("c.example.org", "203.0.113.3")]], count=3)
    summary = runner.run()
    assert (summary.sent, summary.duplicate, summary.rejected, summary.stored) == (3, 1, 1, 1)
    assert summary.ok is False


def test_a_refused_key_stops_the_run():
    client = ScriptedClient([SendResult(api_client.AUTH_FAILED, 401, "Invalid API key")])
    runner = make_runner(client, [[], [a("a.example.org", "203.0.113.1")], [a("b.example.org", "203.0.113.2")]])
    summary = runner.run()
    assert summary.aborted and "API key" in summary.aborted
    assert len(client.sent) == 1


def test_backend_outages_are_retried_without_losing_the_lookup():
    down = SendResult(api_client.ERROR, None, "connection refused")
    client = ScriptedClient([down, stored(7)])
    runner = make_runner(client, [[], [a("a.example.org", "203.0.113.1")], []])
    assert runner.step() is True
    assert runner.step() is True
    assert len(runner.pending) == 1
    assert runner.step() is True
    assert (len(runner.pending), runner.summary.stored) == (0, 1)
    assert client.sent[0]["timestamp"] == client.sent[1]["timestamp"]


def test_too_many_consecutive_errors_end_the_run():
    client = ScriptedClient([SendResult(api_client.ERROR, None, "down")])
    runner = make_runner(client, [[], [a("a.example.org", "203.0.113.1")]] + [[]] * 5, max_consecutive_errors=3)
    summary = runner.run()
    assert summary.aborted and "errors" in summary.aborted


def test_an_unreadable_cache_is_retried_and_then_the_run_stops():
    def broken():
        raise LocalCollectorError("could not read the DNS cache")

    runner = LocalRunner(ScriptedClient([stored()]), settings(), read_cache=broken, out=lambda line: None, sleep=lambda s: None, now=lambda: NOW)
    summary = runner.run()
    assert summary.aborted == "could not read the DNS cache"


def test_ctrl_c_stops_cleanly():
    def interrupt():
        raise KeyboardInterrupt

    runner = LocalRunner(ScriptedClient([stored()]), settings(), read_cache=interrupt, out=lambda line: None, sleep=lambda s: None, now=lambda: NOW)
    summary = runner.run()
    assert summary.stopped_by_user and summary.aborted is None


def test_the_api_key_never_appears_in_output():
    lines = []
    client = ScriptedClient([stored()])
    runner = LocalRunner(client, settings(), read_cache=iter([[], [a("a.example.org", "203.0.113.1")]]).__next__, out=lines.append, sleep=lambda s: None, now=lambda: NOW)
    runner.step()
    runner.step()
    assert lines and all("nm_" not in line for line in lines)
