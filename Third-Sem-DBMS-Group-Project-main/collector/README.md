# Collector simulator

A Python client that sends **synthetic** network metadata to the backend, so the whole system can be
demonstrated without monitoring a real network.

> **By default this is a simulator, not a packet sniffer.** It observes nothing. It invents "device X reached
> destination Y at time T" events for the seeded demo devices, using only documentation/private IP ranges. It
> sends metadata only: no packet capture, credentials, message content, payloads or discovery of any kind. The optional `local` and `local-dns` modes (see "Real Local Collector" below) are the exception:
> they read only this computer's own TCP connection table or DNS cache.

```text
collector.py  ->  POST /api/collector/events  ->  FastAPI  ->  SQLAlchemy  ->  MySQL (network_history)
                  (X-API-Key header)               30-second de-duplication happens in the backend
```

## Setup

```bash
cd collector
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env   (then edit if needed)
```

The backend must be running (`uvicorn app.main:app --port 8000` in `backend/`) with the database created and
seeded (`database/schema.sql`, `database/seed.sql`).

## Run it

```bash
python collector.py                       # simulate until Ctrl+C (one event every 2 s)
python collector.py run --count 50        # send 50 events, then stop
python collector.py run --interval 0.5 --duplicate-rate 0.3
python collector.py run --profile lab-b   # simulate Computer Lab B (use LAB-B's key!)
python collector.py demo-dedup            # demonstrate the 30-second rule, step by step
python collector.py check                 # verify the backend and API key; stores nothing
python collector.py local                 # REAL TCP connection metadata of this Windows computer only
python collector.py --help
```

Leave it running and open the dashboard: new events, activity counts, charts and recent history update on
their own (the dashboard refreshes every 15 seconds).

### What you will see

```text
08:40:05  #0001  STORED     PC-LAB-A-003 -> google.com  event 960
08:40:08  #0003  DUPLICATE  PC-LAB-A-003 -> google.com  repeat of event 960 [intended repeat]
08:40:10  #0009  REJECTED   PC-LAB-A-001 -> example.com  422: deviceIp: must be a valid IPv4 or IPv6 address
...
Summary: 40 sent | 23 stored | 17 duplicate (not stored) | 0 rejected | 0 error(s) | 13.1s
```

- **STORED**: recorded in `network_history` (HTTP 201).
- **DUPLICATE**: the same device reached the same destination within 30 seconds of a stored event, so it was
  not stored (HTTP 200; not an error). `[intended repeat]` marks events the simulator deliberately repeated.
- **REJECTED**: the backend refused the event (for example invalid data). The run continues.
- **AUTH FAIL**: the API key is wrong or revoked (401) or the node is disabled (403). The run stops, because
  retrying cannot help.
- **ERROR**: the backend could not be reached or failed (network error, 5xx). The simulator retries with a
  growing delay and stops after `COLLECTOR_MAX_ERRORS` failures in a row.

The exit code is `0` for a clean run, `1` if any event was rejected or the run had to stop, and `2` for a
configuration error.

## The 30-second demonstration

```bash
python collector.py demo-dedup
```

sends one device to one destination at +0, +5, +12, +25, +30, +40 and +71 seconds and compares the backend's
answer with the rule: `STORED, DUPLICATE, DUPLICATE, DUPLICATE, DUPLICATE, STORED, STORED`. Each run uses a
fresh demo destination (`dedup-demo-HHMMSS.example`) so runs never interfere with each other.

## Configuration

Settings come from environment variables, or from `collector/.env` (environment variables win). Command-line
flags override both. **The API key is only ever read from the environment or `.env`; there is deliberately no
flag for it, and it is never printed or logged.**

| Variable | Default | Flag | Meaning |
|---|---|---|---|
| `COLLECTOR_API_KEY` | *(required)* | | Collector API key of **one** node |
| `COLLECTOR_BACKEND_URL` | `http://127.0.0.1:8000` | `--backend-url` | Where the backend runs |
| `COLLECTOR_PROFILE` | `lab-a` | `--profile` | `lab-a`, `lab-b`, `lib-01` or `admin-01` |
| `COLLECTOR_INTERVAL` | `2` | `--interval` | Seconds between events |
| `COLLECTOR_COUNT` | `0` | `--count` | Events to send; `0` = until Ctrl+C |
| `COLLECTOR_DUPLICATE_RATE` | `0.15` | `--duplicate-rate` | Share (0-1) of deliberate repeats |
| `COLLECTOR_TIMEOUT` | `5` | `--timeout` | Request timeout, seconds |
| `COLLECTOR_MAX_ERRORS` | `10` | | Stop after this many consecutive failures |
| `COLLECTOR_SEED` | *(random)* | `--seed` | Fix the randomness for a reproducible run |

Example `collector/.env`:

```ini
COLLECTOR_BACKEND_URL=http://127.0.0.1:8000
COLLECTOR_API_KEY=nm_dev_lab-a_key
COLLECTOR_PROFILE=lab-a
COLLECTOR_INTERVAL=2
COLLECTOR_COUNT=0
COLLECTOR_DUPLICATE_RATE=0.15
```

### Keys and profiles must match

The backend derives the node from the API key, and the collector never sends a node id. The **profile** only
chooses which device names to simulate, so it must be the profile of the node that owns the key:

| Profile | Node | Development key (from `database/seed.sql`) | Devices |
|---|---|---|---|
| `lab-a` | Computer Lab A | `nm_dev_lab-a_key` | PC-LAB-A-001 to 005 |
| `lab-b` | Computer Lab B | `nm_dev_lab-b_key` | PC-LAB-B-001 to 005 |
| `lib-01` | Library | `nm_dev_lib-01_key` | PC-LIB-001 to 004 |
| `admin-01` | Administrative Block | `nm_dev_admin-01_key` | PC-ADMIN-001 to 003 |

These are development-only keys. If a key and profile do not match, the backend cannot tell: it would create
the profile's device names as new devices under the key's node.

## Real Local Collector (`local`)

`python collector.py local` reports the **TCP connections of the Windows computer it runs on**, using real values
from Windows instead of invented events. It sends them through the same `POST /api/collector/events` endpoint as the
simulator; the backend, its API-key check and its 30-second rule are unchanged.

```bash
python collector.py check                 # backend reachable, key accepted
python collector.py local --interval 2    # inspect the TCP table every 2 seconds
python collector.py local --include-existing   # also report connections that are already open at start
```

It prints, for example:

```text
Local collector -> http://127.0.0.1:8000  (API key: configured)
Backend: reachable
API key: accepted
Device: MY-PC
Watching local TCP connections of this computer (metadata only; no other devices).
Press Ctrl+C to stop.

11:08:31  #0001  STORED     MY-PC -> example.org  event 1490
11:08:33  #0002  DUPLICATE  MY-PC -> 203.0.113.9:443  repeat of event 1489
```

**Simulator vs real collector**

| | Simulator | Real local collector |
|---|---|---|
| Command | `python collector.py` | `python collector.py local` |
| Data | invented for demos | real values from this computer's TCP table |
| Devices | the seeded lab computers | this computer only |
| Protocol / ports | not sent (dashboard shows a dash) | `TCP`, this computer's port, the remote port |
| Needs | nothing | Windows |

**One-time setup.** Create a node and key for this computer (from `backend/`, with the backend's virtual
environment active; the plain key is shown once), then give it to the collector through the environment. The key is
never hard-coded and never printed:

```bash
python create_collector_key.py --node-code HOME-PC --node-name "My Computer" --location "Home"
```

```powershell
$env:COLLECTOR_API_KEY="nm_the-key-you-were-shown"
```

The device is named by `COLLECTOR_DEVICE_ID` if set, otherwise by this computer's host name (never by its IP address,
which can change). The node always comes from the API key. `COLLECTOR_PROFILE` and `COLLECTOR_DEVICE_IP` are not used
by this mode; each event carries the connection's own local address.

**What it collects**, per newly seen outbound TCP connection, exactly as Windows reports it: this computer's IP
address and port, the remote IP address and port, the protocol (`TCP`), the time it was noticed, and a domain when one
can be determined. **It does not collect** packet contents, HTTP/HTTPS data, passwords, cookies, tokens, messages,
keystrokes, process names or ids, or anything about other devices.

**Data source and permissions.** The Windows IP Helper API (`GetExtendedTcpTable` in `iphlpapi.dll`), called through
Python's standard `ctypes`: a structured table, not scraped command output. It needs **no administrator rights** (verified
in a normal, non-elevated terminal), no Npcap, no Scapy, and no extra Python packages. IPv4 uses the table variant
that has no process column at all; IPv6 only has a variant that includes a process id, which is discarded while parsing
and never stored or sent.

**Which connections count.** Only `ESTABLISHED` connections this computer opened: connections to a port this
computer is itself listening on are treated as inbound and skipped (Windows does not say who started a connection),
as are connections to loopback, link-local, multicast or unspecified addresses and to this computer's own address.
A connection is reported once, when it first appears. Its local/remote address-and-port tuple is used only to
recognise that same live connection on later polls, and is forgotten when the connection closes.

**How the domain is chosen.** The TCP table has IP addresses only. The domain comes from the existing Windows
DNS-cache reader and is used **only when exactly one cached name maps to that remote IP**. A shared address (a CDN
or cloud front end) is used by many names, so it is sent with `domain: null` rather than an arbitrary name. There are
no reverse-DNS lookups. An event is never changed after it has been sent, so a domain learned later does not rewrite
earlier events; it only helps later connections. If the DNS cache cannot be read, domains are simply `null`.

**Deduplication.** The collector suppresses only repeats of the *same live connection*. The backend's existing rule
(same device + same destination within 30 seconds = duplicate) is unchanged and authoritative; protocol and ports are
not part of it, so several connections to one server within 30 seconds are stored as one event.

**Errors.** One unreadable or malformed connection never stops the run. A temporary failure reading the table, an
unreadable DNS cache, a rejected or invalid event, or a backend that is briefly down are all tolerated: events wait in
a queue and are retried with a growing delay (up to 30 seconds) and their original observation time, and the run only
ends after `COLLECTOR_MAX_ERRORS` consecutive failures or if the API key is refused. Ctrl+C stops it cleanly with a summary.

**Limitations**

- **This collector does not monitor other devices on the network.** It sees only the computer it runs on: not other
  laptops, phones, other users on the Wi-Fi, or traffic passing through the router.
- **TCP only.** UDP has no connection table, so UDP traffic, including QUIC/HTTP3 (used by browsers for many sites), is
  not represented, and a browser visit can be missing entirely.
- It polls a snapshot, so a connection that opens and closes between two polls is missed; browsers pool and reuse
  connections, use their own DNS and DNS-over-HTTPS, and make background connections. It provides **local TCP
  connection visibility, not complete browser history.**
- Only connections that appear after it starts are reported, unless `--include-existing` is given.
- Windows only.

### Real DNS lookups (`local-dns`)

`python collector.py local-dns` is the earlier, name-based mode: it reports the site names this computer looks up,
read from the Windows DNS cache, without ports or protocol. It also reads only this computer and needs no
administrator rights. A site that is still in the cache is not looked up again, so revisits within its cache time are
not seen, and browsers that use their own DNS (for example Chrome's built-in resolver or Secure DNS) can bypass the
Windows cache. Use `local` for connection metadata and `local-dns` for names.

## Tests

```bash
pip install pytest
python -m pytest                          # unit tests: config, generator, client, run loop, CLI
```

The tests that drive this simulator against the real FastAPI app and MySQL are in
`backend/tests/test_collector_simulator.py` (run them with the backend's `python -m pytest`).
