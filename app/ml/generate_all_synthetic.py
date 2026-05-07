"""Generate demand history and recommendation dataset in one run."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.ml.cancellation_risk.train_model import train_and_save as train_cancellation_risk
from app.ml.demand.synthetic_history import generate_synthetic_history
from app.ml.recommendation.synthetic_dataset import OUTPUT_PATH, generate_reco_synthetic_dataset


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate all synthetic ML data (demand + recommendation).")
    parser.add_argument("--history-count", type=int, default=8000, help="Synthetic booking rows for demand history.")
    parser.add_argument("--months-back", type=int, default=6, help="How far back to generate booking history.")
    parser.add_argument("--history-seed", type=int, default=42, help="Random seed for demand history generation.")
    parser.add_argument("--reset-history", action="store_true", help="Delete prior synthetic booking history first.")
    parser.add_argument("--reco-samples", type=int, default=6000, help="Synthetic request/candidate samples for recommendation CSV.")
    parser.add_argument("--reco-seed", type=int, default=42, help="Random seed for recommendation dataset generation.")
    parser.add_argument("--reco-output", type=str, default=str(OUTPUT_PATH), help="Output CSV path for recommendation dataset.")
    parser.add_argument("--train-risk", action="store_true", help="Also train cancellation-risk model from generated history.")
    args = parser.parse_args()

    inserted = generate_synthetic_history(
        count=args.history_count,
        months_back=args.months_back,
        seed=args.history_seed,
        reset=args.reset_history,
    )
    dataset_path = generate_reco_synthetic_dataset(
        samples=args.reco_samples,
        seed=args.reco_seed,
        output_path=Path(args.reco_output),
    )
    print(f"Inserted synthetic demand bookings: {inserted}")
    print(f"Wrote recommendation dataset: {dataset_path}")
    if args.train_risk:
        metadata = train_cancellation_risk()
        print(f"Trained cancellation-risk model on {metadata['rows_total']} rows")


if __name__ == "__main__":
    _cli()
