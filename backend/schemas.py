from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GaugeCalibration(BaseModel):
    """User-supplied scale calibration; angles use image coordinates."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    minimum_value: float
    maximum_value: float
    units: str = Field(min_length=1, max_length=20)
    start_angle_deg: float = Field(ge=0, le=360)
    end_angle_deg: float = Field(ge=0, le=360)
    sweep_direction: Literal["clockwise", "counterclockwise"]
    instrument_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_scale(self) -> "GaugeCalibration":
        if self.maximum_value <= self.minimum_value:
            raise ValueError("maximum_value must be greater than minimum_value")
        clockwise = (self.end_angle_deg - self.start_angle_deg) % 360.0
        span = clockwise if self.sweep_direction == "clockwise" else (360.0 - clockwise) % 360.0
        if span < 20.0 or span > 330.0:
            raise ValueError("calibrated sweep must be between 20 and 330 degrees")
        return self

    @property
    def full_scale(self) -> float:
        return self.maximum_value - self.minimum_value

    @property
    def sweep_degrees(self) -> float:
        clockwise = (self.end_angle_deg - self.start_angle_deg) % 360.0
        return clockwise if self.sweep_direction == "clockwise" else (360.0 - clockwise) % 360.0


class Measurement(BaseModel):
    estimator: Literal["geometric", "polar"]
    pass_number: int = 1
    angle_deg: float
    value: float
    units: str
    in_calibration_range: bool = True
    evidence: dict[str, float | int | str]


class TraceEvent(BaseModel):
    time: str
    state: str
    tool: str
    message: str
    details: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class InspectionResult(BaseModel):
    inspection_id: str
    state: Literal[
        "OBSERVING",
        "MEASURING",
        "VERIFYING",
        "REINSPECTION_REQUIRED",
        "VERIFIED",
        "HUMAN_REVIEW_REQUIRED",
        "UNSUPPORTED_INSTRUMENT",
        "FAILED",
    ]
    attempt_number: int
    reading_value: float | None = None
    units: str | None = None
    normalized_disagreement_pct_fs: float | None = None
    image_quality: dict[str, object] = Field(default_factory=dict)
    geometry: dict[str, object] = Field(default_factory=dict)
    measurements: list[Measurement] = Field(default_factory=list)
    decision_reasons: list[str] = Field(default_factory=list)
    next_action: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    evidence_url: str | None = None
    created_at: str
    expires_at: str
