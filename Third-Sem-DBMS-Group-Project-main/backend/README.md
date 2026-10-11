# Backend (FastAPI)

Layering: `api` (routers) → `services` → `repositories` → SQLAlchemy → MySQL.
Route handlers contain no business logic.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit DATABASE_PASSWORD and JWT_SECRET
```

Create the database first (see the root README), then:

```bash
uvicorn app.main:app --reload --port 8000
```

- `GET /api/health` - API is up
- `GET /api/health/db` - MySQL reachable and all six tables present (503 otherwise); requires sign-in
- Interactive docs: http://localhost:8000/docs

## API

The complete API reference (endpoints, filters, roles, status codes, authentication and the collector contract)
is in [docs/api](../docs/api/README.md). Interactive docs: <http://localhost:8000/docs>.

## Tests

Database tests sign in as the seeded ADMIN/ANALYST via the `client` / `analyst_client` /
`anon_client` fixtures and run against the real MySQL database inside a transaction that is rolled back,
so seeded data is not modified. They are skipped automatically if MySQL is unreachable.
Rolled-back inserts still consume `AUTO_INCREMENT` ids.

```bash
python -m pytest
```

## Notes

- The schema is created only by `database/schema.sql`. The application never creates, drops
  or truncates tables. `database/reset.sql` is never run by the application.
- Alembic is configured (`alembic.ini`, `alembic/env.py`) for future controlled migrations
  only; there are no migration versions yet.
