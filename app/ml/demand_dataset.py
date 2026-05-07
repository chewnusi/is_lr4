"""Backward-compatible imports for demand dataset module."""

from app.ml.demand.demand_dataset import DemandRow, build_hourly_inference_rows, build_training_rows, load_training_rows_from_db

__all__ = ["DemandRow", "build_training_rows", "build_hourly_inference_rows", "load_training_rows_from_db"]
