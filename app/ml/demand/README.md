# Demand Forecasting ML

This module trains and serves the demand forecasting model used by:

- `GET /analytics/demand-forecast`
- `/ui/analytics`

## Files

- `synthetic_history.py` - generates patterned historical bookings directly into SQLite
- `demand_dataset.py` - builds demand feature rows from bookings/resources
- `train_model.py` - trains model + baseline and saves artifacts
- `inference.py` - loads model and predicts hourly demand
- `model_store/` - trained artifacts

## Prerequisites

Run from project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Optionally seed base resources/users if DB is empty:

```bash
uvicorn app.main:app --reload
```

Then stop server after startup seeding finishes.

## Step-by-step Training

1) Generate synthetic historical demand data (bookings)

```bash
python -m app.ml.demand.synthetic_history --count 800 --months-back 3 --reset
```

- `--count`: number of synthetic bookings to insert
- `--months-back`: history range
- `--reset`: clears previously generated synthetic rows first

2) Train demand model

```bash
python -m app.ml.demand.train_model
```

3) Check saved artifacts

```bash
ls app/ml/demand/model_store
```

Expected:

- `demand_model.joblib`
- `demand_model.meta.json`

4) Validate via API (admin)

```bash
uvicorn app.main:app --reload
```

Then call:

```bash
curl "http://127.0.0.1:8000/analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&building=Building%20A&user_id=demo-admin"
```

## Retraining

For a fresh retrain cycle:

1. regenerate synthetic history (`--reset`)
2. rerun `python -m app.ml.demand.train_model`

## Unified Synthetic Generator

If you want one command to regenerate demand history, recommendation CSV, and risk model:

```bash
python -m app.ml.generate_all_synthetic --history-count 12000 --months-back 9 --reset-history --reco-samples 8000 --train-risk
```

