# Booking Recommendation ML

This module trains and serves ranking-style booking recommendations used by:

- `POST /recommendations/booking-options`
- booking create/edit UI recommendation helpers

## Files

- `feature_builder.py` - request/candidate feature engineering
- `synthetic_dataset.py` - generates labeled synthetic recommendation pairs
- `train_model.py` - trains `RandomForestClassifier`, saves metrics/artifacts
- `inference.py` - scores and ranks candidate booking options
- `model_store/` - trained artifacts

## Prerequisites

Run from project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Ensure DB has active resources and at least some bookings (for popularity/demand context):

```bash
uvicorn app.main:app --reload
```

Stop server once startup seeding is done.

## Step-by-step Training

1) Generate synthetic recommendation dataset

```bash
python -m app.ml.recommendation.synthetic_dataset --samples 1200
```

Default output:

- `app/ml/recommendation/reco_training_data.csv`

Optional custom output:

```bash
python -m app.ml.recommendation.synthetic_dataset --samples 1200 --output app/ml/recommendation/my_reco_data.csv
```

2) Train recommendation model

```bash
python -m app.ml.recommendation.train_model
```

Or with custom dataset:

```bash
python -m app.ml.recommendation.train_model --dataset app/ml/recommendation/my_reco_data.csv
```

3) Check saved artifacts

```bash
ls app/ml/recommendation/model_store
```

Expected:

- `reco_model.joblib`
- `reco_model.meta.json`

4) Run API and test recommendations

```bash
uvicorn app.main:app --reload
```

Request example:

```bash
curl -X POST "http://127.0.0.1:8000/recommendations/booking-options?user_id=demo-employee" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "meeting_room",
    "preferred_start_time": "2026-04-10T10:00:00",
    "duration_minutes": 60,
    "attendees_count": 6,
    "purpose_category": "meeting",
    "building": "Building A",
    "top_n": 3
  }'
```

## Retraining

Recommended retraining cycle:

1. regenerate synthetic recommendation dataset
2. retrain model
3. verify new metrics in `reco_model.meta.json`

