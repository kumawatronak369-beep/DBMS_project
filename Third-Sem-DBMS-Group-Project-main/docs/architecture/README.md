# Architecture

## Components

```text
                                  +-------------------------------------------+
  Collector simulator             |             FastAPI backend               |
  (per node, API key)             |                                           |
  +----------------+   HTTPS      |  api/        routers (HTTP only)          |
  | event_generator|  ---------->  |    |                                      |
  | api_client     |  X-API-Key   |  services/   business rules, transactions |
  +----------------+              |    |                                      |
                                  |  repositories/  SQL via SQLAlchemy        |
  React dashboard                 |    |                                      |
  +----------------+   JWT        +----v--------------------------------------+
  | pages, hooks,  |  ---------->                     |
  | services/api.js|  Bearer                          v
  +----------------+                          MySQL 8+  (network_monitor)
```

| Layer | Responsibility | Never does |
|---|---|---|
| Router (`app/api`) | Parse the request, call one service, return a schema | Contain business logic |
| Service (`app/services`) | Rules, validation beyond types, transactions, authorization checks that depend on data | Write SQL |
| Repository (`app/repositories`) | All SQL, expressed with SQLAlchemy | Commit a transaction |
| Frontend | Render and call the API through `services/` | Talk to MySQL; act as the security boundary |

## Two kinds of caller, two kinds of credential

- **People** sign in with email and password (`POST /api/auth/login`) and receive a short-lived JWT holding only
  their user id. On every request the backend loads the user, so disabling an account or changing a role takes
  effect immediately. Roles: `ADMIN` (manage nodes and users) and `ANALYST` (read everything else).
- **Collectors** send an `X-API-Key`. Only its SHA-256 hash is stored. The key belongs to exactly one node, and the
  backend takes the node from the key. A `nodeId` in the payload is rejected, and devices are always looked up
  inside the key's own node.

## How one collector event is processed

`POST /api/collector/events` runs as a single database transaction:

```text
authenticate API key  ->  node from key (must not be INACTIVE)
        |
resolve device        (node + deviceIdentifier; create if new)
resolve destination   (ip + domain, NULL-safe; create if new)
        |
30-second check   same device + same destination, a stored event within 30 s?
        |-- yes --> respond 200 DUPLICATE, store nothing
        |-- no
insert network_history   ->  update device / destination / node last_seen  ->  COMMIT
```

Any failure rolls the whole transaction back, so there are never half-stored events. Rows are locked in a fixed
order (node, device, destination) so two collectors reporting at the same moment cannot deadlock or both slip past
the duplicate check. A transient lock failure returns 503 with nothing stored, and resending is safe because
duplicates are detected.

## How the dashboard gets its data

Every number on screen comes from a dedicated aggregate query in the backend (`app/repositories/stats_repository.py`
and friends), never from downloading history to the browser. Lists are paginated by the backend, and filters,
search and date ranges are applied in SQL. The dashboard polls the API every 15 seconds.

## Failure behaviour

- The API returns consistent JSON errors (`{"detail": ...}`), never a stack trace. Validation errors do not echo
  the submitted values (so a rejected password is never sent back).
- The frontend shows a skeleton while loading, a specific empty state for no results, and an error state with a
  retry for failures. An expired session returns the user to the login page. If a background refresh fails, the
  last data stays on screen with one notice.
- The collector retries transient failures with a growing delay, and stops on authentication failures.
