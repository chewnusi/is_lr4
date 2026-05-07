"""Synthetic recommendation dataset generator."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine
from app.ml.recommendation.feature_builder import CandidateOption, RecommendationRequest, candidate_to_features, check_availability, generate_candidate_offsets
from app.models_db import Booking, Resource

OUTPUT_PATH = Path(__file__).resolve().parent / "reco_training_data.csv"


def _popularity_by_resource(bookings: list[Booking]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for booking in bookings:
        counts[booking.resource_id] = counts.get(booking.resource_id, 0) + 1
    max_count = max(counts.values()) if counts else 1
    return {resource_id: count / max_count for resource_id, count in counts.items()}


def _demand_by_hour(bookings: list[Booking]) -> dict[int, int]:
    demands: dict[int, int] = {}
    for booking in bookings:
        demands[booking.start_time.hour] = demands.get(booking.start_time.hour, 0) + 1
    return demands


def _acceptance_probability(features: dict) -> float:
    score = 0.0
    score += 0.25 if features["is_available"] else -0.5
    score += 0.20 if features["type_match"] else -0.25
    score += 0.15 if features["building_match"] else 0.0
    score += max(-0.25, 0.2 - features["time_difference_minutes"] / 240.0)
    score += max(-0.3, min(0.2, features["capacity_gap"] / 25.0))
    score += min(0.2, features["historical_popularity"] * 0.2)
    score += -0.1 if features["is_peak_hour"] and features["current_demand_at_hour"] > 10 else 0.05
    return min(0.98, max(0.02, 0.5 + score))


def generate_reco_synthetic_dataset(samples: int = 1200, seed: int = 42, output_path: Path = OUTPUT_PATH) -> Path:
    random.seed(seed)
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as session:
        resources = session.exec(select(Resource).where(Resource.is_active == True)).all()  # noqa: E712
        bookings = session.exec(select(Booking)).all()
    if not resources:
        raise RuntimeError("No active resources found.")

    popularity = _popularity_by_resource(bookings)
    hourly_demand = _demand_by_hour(bookings)
    purpose_categories = ["meeting", "workshop", "presentation", "training", "interview", "planning", "support", "maintenance", "event", "other"]

    rows: list[dict] = []
    for _ in range(samples):
        target_resource_type = random.choice([resource.type for resource in resources])
        preferred_start = now + timedelta(days=random.randint(1, 30), hours=random.randint(7, 18))
        duration = random.choice([30, 60, 90, 120, 180])
        attendees = random.randint(1, 16)
        req_building = random.choice([resource.building for resource in resources if resource.building] + [None])
        request = RecommendationRequest(
            resource_type=target_resource_type,
            preferred_start_time=preferred_start,
            duration_minutes=duration,
            attendees_count=attendees,
            purpose_category=random.choice(purpose_categories),
            building=req_building,
        )
        candidate_resources = random.sample(resources, k=min(10, len(resources)))
        for resource in candidate_resources:
            for offset in generate_candidate_offsets():
                candidate_start = preferred_start + offset
                candidate_end = candidate_start + timedelta(minutes=duration)
                available = check_availability(bookings, resource.id, candidate_start, candidate_end)
                candidate = CandidateOption(
                    resource=resource,
                    start_time=candidate_start,
                    end_time=candidate_end,
                    is_available=available,
                    current_demand_at_hour=hourly_demand.get(candidate_start.hour, 0),
                    historical_popularity=popularity.get(resource.id, 0.0),
                )
                features = candidate_to_features(request, candidate)
                probability = _acceptance_probability(features)
                features["accepted"] = 1 if random.random() < probability else 0
                features["candidate_start_time"] = candidate_start.isoformat()
                features["candidate_end_time"] = candidate_end.isoformat()
                rows.append(features)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return output_path


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic recommendation dataset.")
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    args = parser.parse_args()
    path = generate_reco_synthetic_dataset(samples=args.samples, seed=args.seed, output_path=Path(args.output))
    print(f"Wrote recommendation dataset: {path}")


if __name__ == "__main__":
    _cli()
