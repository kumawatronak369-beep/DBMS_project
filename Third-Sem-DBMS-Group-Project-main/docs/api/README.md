# API reference

All routes live under `/api`. This page is the reference; the running backend also serves interactive
OpenAPI docs at `/docs` (and the schema at `/openapi.json`). Responses use JSON. Errors are `{"detail": ...}`
and never include a stack trace.

## Endpoints

All routes are under `/api`; interactive docs at `/docs`. Lists are paginated by the backend
(`page`, `pageSize` up to 100) and return `{items, total, page, page_size}`.

| Area | Endpoints |
|---|---|
| Nodes | `GET /nodes` (`search`, `status`), `GET /nodes/{id}`, `POST /nodes`, `PUT /nodes/{id}`, `PATCH /nodes/{id}/status` |
| Devices | `GET /devices` (`search`, `nodeId`, `status`), `GET /devices/{id}`, `GET /devices/{id}/history` |
| Destinations | `GET /destinations` (`search`, `category`), `GET /destinations/{id}`, `GET /destinations/{id}/history` |
| History | `GET /history` (`q`, `device`, `deviceId`, `nodeId`, `destinationId`, `domain`), `GET /history/{id}` |
| Dashboard | `GET /dashboard/summary`, `/activity`, `/top-destinations`, `/top-devices` |
| Reports | `GET /reports/top-destinations`, `/top-devices`, `/activity-by-node`, `/activity-over-time` |
| Users (admin) | `GET /users` (`search`, `role`, `status`), `GET /users/{id}`, `POST /users`, `PUT /users/{id}`, `PATCH /users/{id}/status` |

Time filtering: `range=24h|7d|30d`, or `startDate` / `endDate` (ISO date or datetime; a date-only
`endDate` includes the whole day). Bad input returns 400/422, unknown ids 404, duplicate node
codes 409, unexpected failures a generic 500 with no stack trace.

Nodes are never deleted (history is preserved): use `PATCH /nodes/{id}/status`.

Every route above (except the public ones) requires a signed-in user (see Authentication and roles). Node
create/update/status and `/users` are ADMIN only. The collector endpoint uses API-key authentication (see Collector API).

## Authentication and roles

- `POST /api/auth/login` `{email, password}` returns a short-lived JWT (`Authorization: Bearer <token>`),
  its lifetime and the user. `GET /api/auth/me` returns the current user. `POST /api/auth/logout`
  returns 204: tokens are stateless, so the client simply discards its token.
- Passwords are hashed with bcrypt and are never stored, returned or logged. Wrong-password and
  unknown-email logins return the same 401. A disabled account gets 403, but only after the correct
  password is supplied.
- Tokens carry only the user id. The role and status are read from the database on every request,
  so disabling a user or changing a role takes effect immediately.
- The API refuses to start unless `JWT_SECRET` is at least 32 characters (see `.env.example`).

| Role | Permissions |
|---|---|
| ANALYST | Read the dashboard, nodes, devices, history, destinations and reports |
| ADMIN | Everything an analyst can do, plus create/edit/disable nodes and manage users (`/api/users`) |

Public routes: `GET /api/health` and `POST /api/auth/login`. `GET /api/health/db` needs a signed-in user. Everything else
returns 401 without a valid token; ADMIN-only routes return 403 for analysts. The last active
administrator cannot be disabled or demoted. Not implemented: login rate limiting and server-side
token revocation.

## Collector API

`POST /api/collector/events` with header `X-API-Key: <key>`:

```json
{"deviceIdentifier": "PC-LAB-A-001", "deviceIp": "192.168.10.21",
 "destinationIp": "203.0.113.10", "domain": "example.com", "timestamp": "2026-09-19T20:15:32"}
```

| Status | Meaning |
|---|---|
| 201 | Stored: `{"status": "STORED", "history_id": ...}` |
| 200 | Duplicate within 30 seconds, not stored: `{"status": "DUPLICATE", "duplicate_of": ...}` |
| 401 | Missing, unknown or revoked API key (one message for all three) |
| 403 | The key's node is disabled (`INACTIVE`) |
| 422 | Invalid payload, unknown field (including any `nodeId`), or a timestamp more than 5 minutes ahead |
| 503 | Transient lock failure: nothing was stored, resend is safe |

**Optional connection metadata.** A collector that can observe a connection may also send `protocol`
(`"TCP"` or `"UDP"`), `sourcePort` and `destinationPort` (integers 1-65535); ports require a protocol. They are
stored with the event, returned by the history endpoints as `protocol`, `source_port` and `destination_port`, and
are `null` for events that have none (the simulator, DNS-only collectors, and all events stored before these
fields existed). They are **not** part of the 30-second rule, which is still device + destination only.

```json
{"deviceIdentifier": "MY-PC", "deviceIp": "192.168.1.3", "destinationIp": "203.0.113.9", "domain": null,
 "timestamp": "2026-09-21T11:08:30", "protocol": "TCP", "sourcePort": 56188, "destinationPort": 443}
```

- **Node**: derived from the API key only. A `nodeId` in the payload is rejected, and a device
  identifier is always resolved inside the key's own node, so a collector cannot write to another
  node. Only a SHA-256 hash of each key is stored (`collector_api_keys.key_hash`); keys are never
  logged or returned.
- **Device**: found by node + `deviceIdentifier`, created if new. A changed IP is the same device;
  the newest observation updates its IP.
- **Destination**: found by IP + domain (a missing domain is NULL), created if new with category
  `UNKNOWN`. Domains are lower-cased and IPs canonicalised.
- **30-second rule**: a stored event for the same device and destination within 30 seconds
  (inclusive) makes the new one a duplicate. The window is checked on both sides so a late-arriving
  old event is judged against its neighbours, not against newer events days away; for in-order
  events this is identical to the specification's lower-bound query.
- **Transaction**: one transaction per event: node/device/destination resolution, duplicate check,
  history insert, `last_seen` updates (never moved backwards). Any failure rolls all of it back.
  Rows are locked in a fixed order (node, device, destination) so concurrent events neither deadlock
  nor both pass the duplicate check.
- `OFFLINE` nodes may still report. Node status is never changed by events.
