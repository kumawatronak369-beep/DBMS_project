"""Collector for the demo: sends network metadata to the backend.

    python collector.py                  simulate until Ctrl+C
    python collector.py run --count 50   send 50 events, then stop
    python collector.py demo-dedup       show the 30-second rule
    python collector.py check            check the backend and API key
    python collector.py local            TCP connections of this Windows PC
    python collector.py local-dns        DNS lookups of this Windows PC

Settings come from environment variables or collector/.env.
"""

import argparse
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import config
import event_generator
import local_collector
import tcp_collector
from api_client import AUTH_FAILED, DUPLICATE, ERROR, KEY_OK, REJECTED, STORED, CollectorClient

MAX_BACKOFF_SECONDS = 30

# (seconds after the first event, expected outcome)
DEMO_SEQUENCE = [
    (0, STORED),
    (5, DUPLICATE),
    (12, DUPLICATE),
    (25, DUPLICATE),
    (30, DUPLICATE),  # exactly 30 seconds still counts as a duplicate
    (40, STORED),
    (71, STORED),
]


@dataclass
class Summary:
    sent: int = 0
    stored: int = 0
    duplicate: int = 0
    rejected: int = 0
    errors: int = 0
    aborted: str | None = None
    stopped_by_user: bool = False
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.aborted is None and self.rejected == 0

    def line(self) -> str:
        parts = [
            f"{self.sent} sent",
            f"{self.stored} stored",
            f"{self.duplicate} duplicate (not stored)",
            f"{self.rejected} rejected",
            f"{self.errors} error(s)",
            f"{self.elapsed:.1f}s",
        ]
        return "Summary: " + " | ".join(parts)


class Simulator:
    def __init__(self, client, generator, settings, out=print, sleep=time.sleep, monotonic=time.monotonic):
        self.client = client
        self.generator = generator
        self.settings = settings
        self.out = out
        self.sleep = sleep
        self.monotonic = monotonic

    def _report(self, number: int, event, result, extra: str = "") -> None:
        payload = event.payload
        destination = payload.get("domain") or f"{payload['destinationIp']} (no domain)"
        label = {AUTH_FAILED: "AUTH FAIL"}.get(result.outcome, result.outcome)
        if result.outcome == STORED:
            detail = f"event {result.history_id}"
        elif result.outcome == DUPLICATE:
            detail = f"repeat of event {result.duplicate_of}"
        else:
            detail = f"{result.status_code or '-'}: {result.message}"
        repeat = " [intended repeat]" if event.is_repeat else ""
        clock = payload["timestamp"][11:19]
        self.out(f"{clock}  #{number:04d}  {label:<9}  {payload['deviceIdentifier']} -> {destination}  {detail}{repeat}{extra}")

    def run(self) -> Summary:
        settings, summary = self.settings, Summary()
        started = self.monotonic()
        consecutive_errors = 0
        number = 0
        try:
            while settings.count == 0 or number < settings.count:
                event = self.generator.next_event()
                number += 1
                result = self.client.send_event(event.payload)
                summary.sent += 1

                if result.outcome == STORED:
                    summary.stored += 1
                elif result.outcome == DUPLICATE:
                    summary.duplicate += 1
                elif result.outcome == REJECTED:
                    summary.rejected += 1
                elif result.outcome == ERROR:
                    summary.errors += 1

                if result.outcome == ERROR:
                    consecutive_errors += 1
                    if consecutive_errors >= settings.max_consecutive_errors:
                        self._report(number, event, result)
                        summary.aborted = f"stopped after {consecutive_errors} consecutive errors"
                        break
                    wait = min(MAX_BACKOFF_SECONDS, max(settings.interval, 0.5) * 2 ** (consecutive_errors - 1))
                    self._report(number, event, result, f"  (retrying in {wait:.1f}s, {consecutive_errors}/{settings.max_consecutive_errors})")
                    self.sleep(wait)
                    continue

                consecutive_errors = 0
                self._report(number, event, result)
                if result.outcome == AUTH_FAILED:
                    summary.aborted = f"authentication failed ({result.status_code}); retrying cannot help"
                    break
                if settings.count == 0 or number < settings.count:
                    self.sleep(settings.interval)
        except KeyboardInterrupt:
            summary.stopped_by_user = True
        summary.elapsed = self.monotonic() - started
        return summary


def run_dedup_demo(client, profile, now=datetime.now, out=print) -> bool:
    device = profile.devices()[0]
    current = now().replace(microsecond=0)
    destination = event_generator.SimDestination("198.51.100.200", f"dedup-demo-{current:%H%M%S}.example", 1)
    base = current - timedelta(minutes=3)

    out(f"30-second rule demo: {device.identifier} -> {destination.domain}")
    out(f"{'time':<10}{'offset':>8}  {'expected':<10}{'actual':<10}result")
    all_as_expected = True
    for offset, expected in DEMO_SEQUENCE:
        stamp = base + timedelta(seconds=offset)
        result = client.send_event(event_generator.build_payload(device, destination, stamp))
        matches = result.outcome == expected
        all_as_expected &= matches
        out(f"{stamp:%H:%M:%S}  {'+' + str(offset) + 's':>8}  {expected:<10}{result.outcome:<10}{'ok' if matches else 'MISMATCH ' + result.message}")
    out("Result: " + ("the backend applied the 30-second rule as specified." if all_as_expected else "UNEXPECTED outcomes, see above."))
    return all_as_expected


def run_check(client, out=print) -> bool:
    if not client.check_health():
        out("Backend: NOT reachable")
        return False
    out("Backend: reachable")
    result = client.check_api_key()
    if result.outcome == KEY_OK:
        out("API key: accepted")
        return True
    out(f"API key: NOT accepted ({result.status_code or '-'}: {result.message})")
    return False


def _finish_local(summary) -> int:
    print()
    if summary.stopped_by_user:
        print("Stopped by user.")
    if summary.aborted:
        print(f"Aborted: {summary.aborted}")
    print(summary.line())
    return 0 if summary.ok else 1


def run_local_tcp(client, settings, include_existing=False) -> int:
    print(f"Local collector -> {settings.backend_url}  (API key: configured)")
    if not run_check(client):
        return 1
    try:
        tcp_collector.read_tcp_table()
    except tcp_collector.TcpTableError as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 1
    runner = tcp_collector.TcpRunner(client, settings, include_existing=include_existing)
    print(f"Device: {runner.device_id}")
    print("Watching local TCP connections of this computer (metadata only; no other devices).")
    print("Press Ctrl+C to stop.")
    print()
    return _finish_local(runner.run())


def run_local_dns(client, settings) -> int:
    print(f"Local DNS collector -> {settings.backend_url}  (API key: configured)")
    if not run_check(client):
        return 1
    runner = local_collector.LocalRunner(client, settings)
    print(f"Device: {runner.device_id} ({runner.device_ip})")
    print("Watching this computer's DNS lookups (site names only). Open some websites; press Ctrl+C to stop.")
    print()
    return _finish_local(runner.run())


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="collector.py",
        description="Synthetic network-metadata collector for the demo. Reads COLLECTOR_* settings from the "
        "environment or collector/.env; the API key is never taken from the command line.",
    )
    parser.add_argument("mode", nargs="?", default="run", choices=["run", "demo-dedup", "check", "local", "local-dns"])
    parser.add_argument("--backend-url", help="backend base URL (COLLECTOR_BACKEND_URL)")
    parser.add_argument("--profile", choices=sorted(event_generator.PROFILES), help="node whose seeded devices to simulate (COLLECTOR_PROFILE)")
    parser.add_argument("--interval", type=float, help="seconds between events (COLLECTOR_INTERVAL)")
    parser.add_argument("--count", type=int, help="events to send, 0 = until Ctrl+C (COLLECTOR_COUNT)")
    parser.add_argument("--duplicate-rate", type=float, help="share of events that repeat a recent one, 0-1 (COLLECTOR_DUPLICATE_RATE)")
    parser.add_argument("--seed", type=int, help="fix the random generator for a reproducible run (COLLECTOR_SEED)")
    parser.add_argument("--timeout", type=float, help="request timeout in seconds (COLLECTOR_TIMEOUT)")
    parser.add_argument("--include-existing", action="store_true", help="local mode: also report TCP connections that are already open when the collector starts (default: only new ones)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    # show each line as it happens, even when piped
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)
    try:
        settings = config.load_settings().with_overrides(
            backend_url=args.backend_url.rstrip("/") if args.backend_url else None,
            profile=args.profile,
            interval=args.interval,
            count=args.count,
            duplicate_rate=args.duplicate_rate,
            seed=args.seed,
            timeout=args.timeout,
        )
    except config.ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    if args.mode not in ("local", "local-dns") and settings.profile not in event_generator.PROFILES:
        print(f"Configuration error: unknown profile '{settings.profile}'. Choose one of: "
              f"{', '.join(sorted(event_generator.PROFILES))}", file=sys.stderr)
        return 2
    if not settings.has_api_key:
        print("Configuration error: COLLECTOR_API_KEY is not set. Put it in collector/.env or the environment "
              "(see collector/.env.example).", file=sys.stderr)
        return 2

    client = CollectorClient(settings.backend_url, settings.api_key, settings.timeout)
    if args.mode == "local":
        return run_local_tcp(client, settings, include_existing=args.include_existing)
    if args.mode == "local-dns":
        return run_local_dns(client, settings)

    profile = event_generator.PROFILES[settings.profile]
    print(f"Collector simulator -> {settings.backend_url}  (profile {profile.name}: {profile.node_label}, API key: configured)")

    if args.mode == "check":
        return 0 if run_check(client) else 1
    if args.mode == "demo-dedup":
        return 0 if run_dedup_demo(client, profile) else 1

    generator = event_generator.EventGenerator(
        profile, random.Random(settings.seed), duplicate_rate=settings.duplicate_rate
    )
    total = str(settings.count) if settings.count else "until Ctrl+C"
    print(f"Sending {total} event(s), one every {settings.interval:g}s, ~{settings.duplicate_rate:.0%} intended repeats\n")
    summary = Simulator(client, generator, settings).run()

    print()
    if summary.stopped_by_user:
        print("Stopped by user.")
    if summary.aborted:
        print(f"Aborted: {summary.aborted}")
    print(summary.line())
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
