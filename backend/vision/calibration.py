from __future__ import annotations

from dataclasses import dataclass

from backend.schemas import GaugeCalibration


@dataclass(frozen=True)
class CalibratedReading:
    value: float
    fraction: float
    in_range: bool
    signed_angle_delta_deg: float


def angle_to_value(angle_deg: float, calibration: GaugeCalibration, tolerance_deg: float = 1.5) -> CalibratedReading:
    """Map a screen-coordinate angle to a linear dial scale without clamping."""
    if calibration.sweep_direction == "clockwise":
        delta = (angle_deg - calibration.start_angle_deg) % 360.0
    else:
        delta = (calibration.start_angle_deg - angle_deg) % 360.0
    span = calibration.sweep_degrees
    fraction = delta / span
    in_range = -tolerance_deg / span <= fraction <= 1.0 + tolerance_deg / span
    if in_range:
        # Tiny endpoint noise is tolerated, but materially out-of-range readings are never clamped.
        fraction = min(1.0, max(0.0, fraction))
    value = calibration.minimum_value + fraction * calibration.full_scale
    signed_delta = delta if delta <= 180.0 else delta - 360.0
    return CalibratedReading(value=value, fraction=fraction, in_range=in_range, signed_angle_delta_deg=signed_delta)
