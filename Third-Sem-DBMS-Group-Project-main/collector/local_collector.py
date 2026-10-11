"""Local DNS collector: reports the sites this computer looks up, read from the Windows DNS cache.

Reads only this computer's own cache (names and IPs): no packets, no page content, no other devices.
"""

import ipaddress
import json
import re
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import event_generator
from api_client import AUTH_FAILED, DUPLICATE, ERROR, REJECTED, STORED

A_RECORD, CNAME_RECORD, AAAA_RECORD = 1, 5, 28
TTL_JITTER = 5  # a TTL that goes up by more than this means a new lookup
MAX_PENDING = 500  # max events queued for retry
MAX_CACHE_FAILURES = 3
MAX_BACKOFF_SECONDS = 30  # max wait between retries

DNS_CACHE_COMMAND = "Get-DnsClientCache | Select-Object Name,Type,Data,TimeToLive | ConvertTo-Json -Compress"

_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
_LOCAL_SUFFIXES = (".local", ".localdomain", ".arpa", ".internal", ".home")


class LocalCollectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Lookup:
    domain: str
    ip: str
    ttl: int = 0

    @property
    def label(self) -> str:
        return self.domain


def read_dns_cache(run=subprocess.run) -> list[dict]:
    if sys.platform != "win32":
        raise LocalCollectorError("the local collector reads the Windows DNS cache, so it runs on Windows only")
    try:
        done = run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", DNS_CACHE_COMMAND],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LocalCollectorError(f"could not run PowerShell ({type(error).__name__})") from None
    if done.returncode != 0:
        raise LocalCollectorError("could not read the DNS cache (Get-DnsClientCache failed)")
    text = (done.stdout or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        raise LocalCollectorError("the DNS cache output was not understood") from None
    return [data] if isinstance(data, dict) else list(data)


def _clean(name) -> str:
    return str(name or "").strip().lower().rstrip(".")


def _reportable_domain(name: str) -> bool:
    if "." not in name or len(name) > 255:
        return False
    if name.endswith(_LOCAL_SUFFIXES) or name.startswith("wpad."):
        return False
    return all(_LABEL.match(label) for label in name.split("."))


def _reportable_ip(address: str) -> str | None:
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return None
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return None  # 0.0.0.0 and ::1 mean blocked or local, not a destination
    return str(ip)


def extract_lookups(rows: list[dict]) -> dict[tuple[str, str], int]:
    """DNS cache rows -> {(domain, destination ip): ttl}, following CNAME chains back to the name that was asked for."""
    aliases: dict[str, list[str]] = {}
    for row in rows:
        if row.get("Type") == CNAME_RECORD:
            aliases.setdefault(_clean(row.get("Data")), []).append(_clean(row.get("Name")))

    def asked_for(name: str) -> set[str]:
        found, stack, seen = set(), [name], set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in aliases:
                stack.extend(aliases[current])
            else:
                found.add(current)
        return found

    lookups: dict[tuple[str, str], int] = {}
    for row in rows:
        if row.get("Type") not in (A_RECORD, AAAA_RECORD):
            continue
        ip = _reportable_ip(str(row.get("Data") or ""))
        if ip is None:
            continue
        ttl = int(row.get("TimeToLive") or 0)
        for domain in asked_for(_clean(row.get("Name"))):
            if _reportable_domain(domain):
                key = (domain, ip)
                lookups[key] = max(ttl, lookups.get(key, 0))
    return lookups


def _one_per_site(lookups: list[Lookup]) -> list[Lookup]:
    chosen: dict[str, Lookup] = {}
    for lookup in sorted(lookups, key=lambda item: (":" in item.ip, item.ip)):
        chosen.setdefault(lookup.domain, lookup)
    return sorted(chosen.values(), key=lambda item: item.domain)


class DnsWatcher:
    def __init__(self):
        self._seen: dict[tuple[str, str], int] | None = None

    def poll(self, current: dict[tuple[str, str], int]) -> list[Lookup]:
        new = []
        if self._seen is not None:  # the first look is only a baseline
            for (domain, ip), ttl in current.items():
                previous = self._seen.get((domain, ip))
                if previous is None or ttl > previous + TTL_JITTER:
                    new.append(Lookup(domain, ip, ttl))
        self._seen = dict(current)
        return _one_per_site(new)


def device_identifier(hostname: str | None = None) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", hostname or socket.gethostname()).upper()[:100] or "LOCAL-PC"


def local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # documentation address, never actually contacted
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


@dataclass
class LocalSummary:
    sent: int = 0
    stored: int = 0
    duplicate: int = 0
    rejected: int = 0
    errors: int = 0
    skipped: int = 0
    aborted: str | None = None
    stopped_by_user: bool = False

    @property
    def ok(self) -> bool:
        return self.aborted is None and self.rejected == 0

    def line(self) -> str:
        skipped = f" | {self.skipped} skipped" if self.skipped else ""
        return (
            f"Summary: {self.sent} sent | {self.stored} stored | {self.duplicate} duplicate (not stored) | "
            f"{self.rejected} rejected | {self.errors} error(s){skipped}"
        )


class LocalRunner:
    def __init__(self, client, settings, read_cache=read_dns_cache, out=print, sleep=time.sleep, now=datetime.now):
        self.client = client
        self.settings = settings
        self.read_cache = read_cache
        self.out = out
        self.sleep = sleep
        self.now = now
        self.device_id = settings.device_id or device_identifier()
        self.device_ip = settings.device_ip or local_ip()
        self.watcher = DnsWatcher()
        self.pending: deque[tuple[Lookup, datetime]] = deque(maxlen=MAX_PENDING)
        self.summary = LocalSummary()
        self.number = 0
        self.cache_failures = 0

    def _payload(self, lookup: Lookup, when: datetime) -> dict:
        return event_generator.validate_event(
            {
                "deviceIdentifier": self.device_id,
                "deviceIp": self.device_ip,
                "destinationIp": lookup.ip,
                "domain": lookup.domain,
                "timestamp": when.replace(microsecond=0).isoformat(),
            }
        )

    def _send_pending(self) -> bool:
        summary = self.summary
        while self.pending:
            lookup, when = self.pending[0]
            try:
                payload = self._payload(lookup, when)
            except ValueError as error:
                self.pending.popleft()
                summary.skipped += 1
                self.out(f"{when:%H:%M:%S}  SKIPPED    {lookup.label}  invalid event ({error})")
                continue
            result = self.client.send_event(payload)
            if result.outcome == ERROR:
                summary.errors += 1
                self.out(f"{when:%H:%M:%S}  ERROR      {lookup.label}  {result.message} (will retry)")
                return summary.errors < self.settings.max_consecutive_errors or self._abort("too many errors in a row")
            self.pending.popleft()
            self.number += 1
            summary.sent += 1
            if result.outcome == STORED:
                summary.stored += 1
                detail = f"event {result.history_id}"
            elif result.outcome == DUPLICATE:
                summary.duplicate += 1
                detail = f"repeat of event {result.duplicate_of}"
            elif result.outcome == REJECTED:
                summary.rejected += 1
                detail = f"{result.status_code or '-'}: {result.message}"
            else:
                detail = f"{result.status_code or '-'}: {result.message}"
            label = "AUTH FAIL" if result.outcome == AUTH_FAILED else result.outcome
            self.out(f"{when:%H:%M:%S}  #{self.number:04d}  {label:<9}  {self.device_id} -> {lookup.label}  {detail}")
            if result.outcome == AUTH_FAILED:
                return self._abort("the API key was refused (wrong, revoked, or node disabled)")
            summary.errors = 0
        return True

    def _abort(self, reason: str) -> bool:
        self.summary.aborted = reason
        return False

    def step(self) -> bool:
        try:
            rows = self.read_cache()
        except LocalCollectorError as error:
            self.cache_failures += 1
            self.out(f"Could not read the DNS cache: {error}")
            return self.cache_failures < MAX_CACHE_FAILURES or self._abort(str(error))
        self.cache_failures = 0
        when = self.now()
        for lookup in self.watcher.poll(extract_lookups(rows)):
            self.pending.append((lookup, when))
        return self._send_pending()

    def _delay(self) -> float:
        if self.summary.errors:
            return min(MAX_BACKOFF_SECONDS, max(self.settings.interval, 1.0) * 2 ** min(self.summary.errors, 5))
        return self.settings.interval

    def run(self) -> LocalSummary:
        limit = self.settings.count
        try:
            while self.step():
                if limit and self.number >= limit:
                    break
                self.sleep(self._delay())
        except KeyboardInterrupt:
            self.summary.stopped_by_user = True
        return self.summary
