"""Local TCP collector: outbound TCP connections of this Windows computer.

Reads the Windows TCP table (GetExtendedTcpTable via ctypes), so no Npcap, Scapy or admin rights are needed.
It collects only IPs, ports, protocol and time, and sees this computer only, not other devices on the network.
"""

import ctypes
import ipaddress
import socket
import struct
import sys
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime

import event_generator
from local_collector import LocalRunner, extract_lookups, read_dns_cache

AF_INET, AF_INET6 = 2, 23
TCP_TABLE_BASIC_ALL = 2  # MIB_TCPTABLE: state, addresses and ports only
TCP_TABLE_OWNER_PID_ALL = 5  # the only IPv6 variant; the pid is discarded
NO_ERROR, ERROR_INSUFFICIENT_BUFFER = 0, 122

STATE_LISTEN, STATE_ESTABLISHED = 2, 5  # MIB_TCP_STATE

_V4_ROW = struct.Struct("<5L")  # state, local addr, local port, remote addr, remote port
_V6_ROW = struct.Struct("<16sLL16sLLLL")  # local addr, scope, port, remote addr, scope, port, state, pid


class TcpTableError(RuntimeError):
    pass


@dataclass(frozen=True)
class TcpRow:
    state: int
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int


@dataclass(frozen=True)
class Connection:
    """Identity of a live connection, used only to avoid re-reporting it on every poll."""

    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int


@dataclass(frozen=True)
class TcpEvent:
    connection: Connection
    domain: str | None

    @property
    def label(self) -> str:
        return self.domain or f"{self.connection.remote_ip}:{self.connection.remote_port}"


def _port(raw: int) -> int:
    return socket.ntohs(raw & 0xFFFF)


def parse_ipv4_table(raw: bytes) -> list[TcpRow]:
    if len(raw) < 4:
        return []
    (count,) = struct.unpack_from("<L", raw, 0)
    rows = []
    for index in range(count):
        offset = 4 + index * _V4_ROW.size
        if offset + _V4_ROW.size > len(raw):
            break  # truncated table: keep the complete rows
        state, local, local_port, remote, remote_port = _V4_ROW.unpack_from(raw, offset)
        try:
            rows.append(
                TcpRow(
                    state,
                    str(ipaddress.IPv4Address(struct.pack("<L", local))),
                    _port(local_port),
                    str(ipaddress.IPv4Address(struct.pack("<L", remote))),
                    _port(remote_port),
                )
            )
        except ValueError:
            continue
    return rows


def parse_ipv6_table(raw: bytes) -> list[TcpRow]:
    if len(raw) < 4:
        return []
    (count,) = struct.unpack_from("<L", raw, 0)
    rows = []
    for index in range(count):
        offset = 4 + index * _V6_ROW.size
        if offset + _V6_ROW.size > len(raw):
            break
        local, _scope, local_port, remote, _scope2, remote_port, state, _pid = _V6_ROW.unpack_from(raw, offset)
        try:
            rows.append(
                TcpRow(
                    state,
                    ipaddress.IPv6Address(local).compressed,
                    _port(local_port),
                    ipaddress.IPv6Address(remote).compressed,
                    _port(remote_port),
                )
            )
        except ValueError:
            continue
    return rows


def _get_extended_tcp_table(family: int, table_class: int) -> bytes:
    try:
        function = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
    except (OSError, AttributeError):
        raise TcpTableError("the Windows IP Helper API is not available") from None
    function.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
    function.restype = wintypes.DWORD

    size = wintypes.DWORD(0)
    buffer = None
    for _ in range(8):
        result = function(buffer, ctypes.byref(size), False, family, table_class, 0)
        if result == NO_ERROR:
            return buffer.raw[: size.value] if buffer is not None else b""
        if result != ERROR_INSUFFICIENT_BUFFER:
            raise TcpTableError(f"GetExtendedTcpTable failed (Windows error {result})")
        buffer = ctypes.create_string_buffer(size.value + 1024)
        size = wintypes.DWORD(len(buffer))
    raise TcpTableError("the TCP table kept changing size; try again")


def read_tcp_table(fetch=_get_extended_tcp_table) -> list[TcpRow]:
    if sys.platform != "win32":
        raise TcpTableError("the local TCP collector reads the Windows TCP table, so it runs on Windows only")
    rows = parse_ipv4_table(fetch(AF_INET, TCP_TABLE_BASIC_ALL))
    try:
        rows += parse_ipv6_table(fetch(AF_INET6, TCP_TABLE_OWNER_PID_ALL))
    except TcpTableError:
        pass  # IPv6 may be disabled; IPv4 is still reported
    return rows


def _reportable_remote(address: str, local: str) -> str | None:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return None
    if str(ip) == local:
        return None
    return str(ip)


def outbound_connections(rows: list[TcpRow]) -> set[Connection]:
    """Established connections this computer opened (not ones accepted on a listening port)."""
    listening = {row.local_port for row in rows if row.state == STATE_LISTEN}
    found = set()
    for row in rows:
        try:
            if row.state != STATE_ESTABLISHED or row.local_port in listening:
                continue
            if not (1 <= row.local_port <= 65535 and 1 <= row.remote_port <= 65535):
                continue
            remote = _reportable_remote(row.remote_ip, row.local_ip)
            local = str(ipaddress.ip_address(row.local_ip))
        except (ValueError, AttributeError, TypeError):
            continue
        if remote is not None:
            found.add(Connection(local, row.local_port, remote, row.remote_port))
    return found


def _send_order(connection: Connection):
    remote = ipaddress.ip_address(connection.remote_ip)
    return (remote.version, int(remote), connection.remote_port, connection.local_port)


def domains_by_ip(dns_rows: list[dict]) -> dict[str, str | None]:
    """{remote ip: domain} from the DNS cache, only where exactly one name maps to the IP."""
    names: dict[str, set[str]] = {}
    for domain, ip in extract_lookups(dns_rows):
        names.setdefault(ip, set()).add(domain)
    return {ip: (next(iter(found)) if len(found) == 1 else None) for ip, found in names.items()}


class TcpRunner(LocalRunner):
    """Polls the TCP table and sends each new outbound connection through the collector API."""

    def __init__(self, client, settings, read_tcp=read_tcp_table, read_cache=read_dns_cache, include_existing=False, **kwargs):
        super().__init__(client, settings, read_cache=read_cache, **kwargs)
        self.read_tcp = read_tcp
        self.include_existing = include_existing
        self._known: set[Connection] | None = None
        self._source_failures = 0
        self._dns_warned = False
        self.device_ip = None

    def _payload(self, event: TcpEvent, when: datetime) -> dict:
        c = event.connection
        return event_generator.validate_event(
            {
                "deviceIdentifier": self.device_id,
                "deviceIp": c.local_ip,
                "destinationIp": c.remote_ip,
                "domain": event.domain,
                "timestamp": when.replace(microsecond=0).isoformat(),
                "protocol": "TCP",
                "sourcePort": c.local_port,
                "destinationPort": c.remote_port,
            }
        )

    def _domains(self) -> dict[str, str | None]:
        try:
            return domains_by_ip(self.read_cache())
        except Exception as error:  # noqa: BLE001
            if not self._dns_warned:
                self._dns_warned = True
                self.out(f"DNS cache unavailable, domains will be empty ({type(error).__name__}: {error})")
            return {}

    def step(self) -> bool:
        try:
            rows = self.read_tcp()
        except TcpTableError as error:
            self._source_failures += 1
            self.out(f"Could not read the TCP connection table: {error}")
            if self._source_failures >= self.settings.max_consecutive_errors:
                return self._abort(str(error))
            return self._send_pending()
        self._source_failures = 0

        current = outbound_connections(rows)
        if self._known is None:  # the first look is only a baseline
            fresh = set(current) if self.include_existing else set()
        else:
            fresh = current - self._known
        self._known = current

        if fresh:
            domains = self._domains()
            when = self.now()
            for connection in sorted(fresh, key=_send_order):
                self.pending.append((TcpEvent(connection, domains.get(connection.remote_ip)), when))
        return self._send_pending()
