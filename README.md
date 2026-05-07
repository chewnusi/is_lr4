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

- `demo-admin` (admin)
- `demo-employee` (employee)
- `demo-employee-001` .. `demo-employee-050` (employee pool)

Default temporary password for seeded users:

- `ChangeMe123!` (override via `SEED_TEMP_PASSWORD`)

UI authentication uses `/ui/login` with session cookie.
For API/testing convenience, you can still pass `?user_id=<id>`.

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
GET /analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&building=Building%20A
```

UI Analytics page:

- `/ui/analytics` (admin login required)

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

Cancellation risk endpoint:

```bash
POST /analytics/cancellation-risk
```

Recommendation model artifacts:

- `app/ml/recommendation/model_store/reco_model.joblib`
- `app/ml/recommendation/model_store/reco_model.meta.json`

## Retraining Workflow (User-Linked)

If users/bookings changed or new real data was collected, retrain in this order:

```bash
python -m app.ml.generate_all_synthetic --history-count 12000 --months-back 9 --reset-history --reco-samples 8000 --train-risk
python -m app.ml.recommendation.train_model
python -m app.ml.demand.train_model
python -m app.ml.cancellation_risk.train_model
```

If you already used `--train-risk`, the last command is optional.

SQLite is fully valid for accumulating real historical data over time. You can keep training from collected SQLite records; later migration to Postgres is straightforward because feature extraction lives at app/ML layer.
