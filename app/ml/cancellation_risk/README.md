# Cancellation Risk ML

This module trains and serves cancellation-risk probability scoring for bookings.

## Files

- `dataset.py` - builds training rows from bookings/resources/users
- `train_model.py` - trains classifier and saves artifacts
- `inference.py` - loads model and scores booking requests/candidates
- `model_store/` - trained artifacts

## Training

From project root:

```bash
source .venv/bin/activate
python -m app.ml.cancellation_risk.train_model
```

Expected artifacts:

- `app/ml/cancellation_risk/model_store/risk_model.joblib`
- `app/ml/cancellation_risk/model_store/risk_model.meta.json`

## API

`POST /analytics/cancellation-risk`

Request fields:

- `user_id`
- `resource_id`
- `start_time`
- `end_time`
- `purpose_category`
- `attendees_count` (optional)

Response:

- `cancellation_risk` (float `0..1`)

## Unified Synthetic Flow

You can generate history/datasets and train risk model in one command:

```bash
python -m app.ml.generate_all_synthetic --history-count 12000 --months-back 9 --reset-history --reco-samples 8000 --train-risk
```

