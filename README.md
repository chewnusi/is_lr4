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
  - Analytics
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

## Demand Forecasting (Analytics)

Generate patterned synthetic history (500-1000+ recommended):

```bash
python -m app.ml.demand.synthetic_history --count 800 --months-back 3 --reset
```

Train the demand model manually:

```bash
python -m app.ml.demand.train_model
```

Model artifacts are saved to:

- `app/ml/demand/model_store/demand_model.joblib`
- `app/ml/demand/model_store/demand_model.meta.json`

Forecast API (admin only):

```bash
GET /analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&building=Building%20A&user_id=demo-admin
```

UI Analytics page:

- `/ui/analytics?user_id=demo-admin`

## Booking Recommendations (ML)

Generate recommendation training dataset:

```bash
python -m app.ml.recommendation.synthetic_dataset --samples 1200
```

Train recommendation model:

```bash
python -m app.ml.recommendation.train_model
```

Recommendation endpoint:

```bash
POST /recommendations/booking-options
```

Recommendation model artifacts:

- `app/ml/recommendation/model_store/reco_model.joblib`
- `app/ml/recommendation/model_store/reco_model.meta.json`
