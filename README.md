# Resource Booking Management System

FastAPI + SQLModel booking system with SQLite, role-based authorization, and server-rendered UI.

## Highlights

- SQLite persistence with SQLModel entities (`resources`, `bookings`, `users`)
- Alembic migration support (`alembic upgrade head`)
- Booking validation:
  - strict datetime parsing
  - rejects past bookings
  - enforces `start_time < end_time`
  - resource existence checks
  - approved-booking conflict detection
- Status lifecycle: `pending`, `approved`, `cancelled`
  - only `pending` can be approved
- Roles:
  - `employee`: own bookings only
  - `admin`: manage resources and approve bookings
- Multi-page UI:
  - Dashboard
  - Resources
  - Bookings
  - Calendar
  - Admin
- Pytest API coverage for CRUD/validation/conflicts/authorization regressions

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open:
- UI: [http://127.0.0.1:8000/ui/dashboard](http://127.0.0.1:8000/ui/dashboard)
- Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Demo users

- `demo-employee` (employee)
- `demo-admin` (admin)

Switch user quickly via query param, for example:
- `/ui/dashboard?user_id=demo-admin`

For API calls, also pass `?user_id=demo-admin` (or `demo-employee`).

## Docker

```bash
docker compose up --build
```

The container runs migrations at startup and stores SQLite data in a named volume.
On first start with an empty DB, demo records are auto-seeded so the system is not blank.

## Tests

```bash
pytest -q
```
