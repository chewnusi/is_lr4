"""Backward-compatible imports for demand synthetic history module."""

from app.ml.demand.synthetic_history import SYNTHETIC_ID_PREFIX, clear_synthetic_bookings, generate_synthetic_history

__all__ = ["SYNTHETIC_ID_PREFIX", "clear_synthetic_bookings", "generate_synthetic_history"]
