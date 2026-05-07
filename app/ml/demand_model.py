"""Backward-compatible imports for demand inference module."""

from app.ml.demand.inference import forecast_by_hour, load_metadata, load_model_artifact

__all__ = ["load_model_artifact", "load_metadata", "forecast_by_hour"]
