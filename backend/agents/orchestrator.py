from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from math import isfinite

import numpy as np
import cv2

from backend.schemas import GaugeCalibration, InspectionResult, Measurement, TraceEvent
from backend.agents.policy import MAX_DISAGREEMENT_PCT_FS
from backend.vision.calibration import angle_to_value
from backend.vision.estimators import (
    NeedleEstimate,
    NeedleNotFound,
    estimate_needle_geometric,
    estimate_needle_polar,
    reinspect_image as contrast_refinement,
)
from backend.vision.evidence import generate_evidence
from backend.vision.localization import GaugeGeometry, locate_gauge
from backend.vision.quality import QualityAssessment, assess_image_quality


MAX_FOLLOW_UPS = 2


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


class InspectionAgent:
    """Deterministic perception-decision-action loop with bounded human follow-up."""

    def inspect(
        self,
        inspection_id: str,
        image: np.ndarray,
        calibration: GaugeCalibration,
        attempt_number: int = 0,
        prior_trace: list[TraceEvent] | None = None,
        created_at: datetime | None = None,
    ) -> tuple[InspectionResult, bytes]:
        created = created_at or utc_now()
        expires = utc_now().replace(microsecond=0)
        # Each observation has a bounded 30 minute retention period, reset after a follow-up.
        from datetime import timedelta

        expires = expires + timedelta(minutes=30)
        trace = list(prior_trace or [])

        def log(state: str, tool: str, message: str, **details: Any) -> None:
            trace.append(TraceEvent(time=iso(utc_now()), state=state, tool=tool, message=message, details=details))

        log("OBSERVING", "reinspect_image" if attempt_number else "inspect_image", "Image observation received.", attempt=attempt_number + 1)
        log("OBSERVING", "assess_image_quality", "OpenCV image-quality indicators measured.")
        quality: QualityAssessment = assess_image_quality(image)
        log("OBSERVING", "assess_image_quality", "Image-quality decision recorded.", usable=quality.usable, flags=",".join(quality.reasons))
        log("OBSERVING", "locate_gauge", "Searching for one circular dial boundary.")
        geometry = locate_gauge(image)

        selected_measurements: list[Measurement] = []
        reading_value: float | None = None
        disagreement: float | None = None
        reasons: list[str] = []
        state: str
        next_action: str | None = None

        if geometry is None:
            log("ESCALATED", "escalate_to_human", "No supported circular dial boundary was found.")
            state = "UNSUPPORTED_INSTRUMENT"
            reasons.append("No supported circular dial could be localized; the system will not infer a reading.")
        elif not quality.usable:
            reasons.extend(f"Image quality concern: {reason.replace('_', ' ')}." for reason in quality.reasons)
            if attempt_number < MAX_FOLLOW_UPS:
                next_action = self.request_new_view(quality.reasons)
                log("REINSPECTION_REQUIRED", "request_new_view", "A new camera observation is needed before measurement.", attempt=attempt_number + 1)
                state = "REINSPECTION_REQUIRED"
            else:
                log("ESCALATED", "escalate_to_human", "Image quality remained insufficient after the retry limit.", attempts=attempt_number + 1)
                state = "HUMAN_REVIEW_REQUIRED"
                reasons.append("The bounded reinspection limit was reached.")
        else:
            log("MEASURING", "locate_gauge", "Gauge geometry passed the boundary checks.", method=geometry.method)
            first_pair, failures = self._estimate_pair(image, geometry, calibration, log, pass_number=1)
            if failures:
                reasons.extend(failures)
            pair = first_pair
            if pair:
                disagreement = self.compare_measurements(pair, calibration)
                log("VERIFYING", "compare_measurements", "Geometric and polar outputs compared.", disagreement_pct_fs=round(disagreement, 3))
                if disagreement > MAX_DISAGREEMENT_PCT_FS:
                    reasons.append(f"Initial estimators disagree by {disagreement:.2f}% of full scale.")
                    log("MEASURING", "reinspect_image", "Disagreement selected a contrast-normalized second pass.")
                    refined = contrast_refinement(image)
                    second_pair, second_failures = self._estimate_pair(refined, geometry, calibration, log, pass_number=2)
                    reasons.extend(second_failures)
                    if second_pair:
                        refined_disagreement = self.compare_measurements(second_pair, calibration)
                        log("VERIFYING", "compare_measurements", "Refined estimator outputs compared.", disagreement_pct_fs=round(refined_disagreement, 3))
                        if refined_disagreement <= MAX_DISAGREEMENT_PCT_FS:
                            pair = second_pair
                            disagreement = refined_disagreement
                        else:
                            pair = []
                            disagreement = refined_disagreement
                    else:
                        pair = []
                if not pair:
                    if attempt_number < MAX_FOLLOW_UPS:
                        next_action = self.request_new_view(("estimator_disagreement",))
                        log("REINSPECTION_REQUIRED", "request_new_view", "Contrast refinement did not resolve the disagreement.", attempt=attempt_number + 1)
                        state = "REINSPECTION_REQUIRED"
                    else:
                        log("ESCALATED", "escalate_to_human", "Estimator disagreement persisted after all allowed observations.", attempts=attempt_number + 1)
                        state = "HUMAN_REVIEW_REQUIRED"
                        reasons.append("Two estimators could not reach the configured agreement threshold.")
                elif not all(item.in_calibration_range for item in pair):
                    reasons.append("At least one estimate falls outside the configured calibration sweep.")
                    if attempt_number < MAX_FOLLOW_UPS:
                        next_action = self.request_new_view(("out_of_range",))
                        log("REINSPECTION_REQUIRED", "request_new_view", "An out-of-range result requires a better observation.", attempt=attempt_number + 1)
                        state = "REINSPECTION_REQUIRED"
                    else:
                        log("ESCALATED", "escalate_to_human", "Out-of-range estimate persisted after the retry limit.")
                        state = "HUMAN_REVIEW_REQUIRED"
                else:
                    selected_measurements = pair
                    reading_value = sum(item.value / len(pair) for item in pair)
                    reasons.append("Image-quality, geometry, calibration-range, and estimator-agreement checks passed.")
                    state = "VERIFIED"
            else:
                reasons.extend(failures or ["Both estimators returned no usable candidate."])
                if attempt_number < MAX_FOLLOW_UPS:
                    next_action = self.request_new_view(("needle_not_found",))
                    log("REINSPECTION_REQUIRED", "request_new_view", "Needle evidence was insufficient.", attempt=attempt_number + 1)
                    state = "REINSPECTION_REQUIRED"
                else:
                    log("ESCALATED", "escalate_to_human", "Needle evidence remained insufficient after all allowed observations.")
                    state = "HUMAN_REVIEW_REQUIRED"

        log("VERIFYING" if state == "VERIFIED" else state, "generate_evidence", "Annotated evidence image generated from a copy of the observation.")
        evidence = generate_evidence(
            image,
            geometry,
            [item.model_dump() for item in selected_measurements],
            state,
            [list(box) for box in quality.glare_boxes],
        )
        result = InspectionResult(
            inspection_id=inspection_id,
            state=state,
            attempt_number=attempt_number + 1,
            reading_value=reading_value,
            units=calibration.units if reading_value is not None else None,
            normalized_disagreement_pct_fs=round(disagreement, 3) if disagreement is not None else None,
            image_quality=quality.as_dict(),
            geometry=geometry.as_dict() if geometry else {},
            measurements=selected_measurements,
            decision_reasons=reasons,
            next_action=next_action,
            trace=trace,
            evidence_url=f"/api/inspections/{inspection_id}/evidence",
            created_at=iso(created),
            expires_at=iso(expires),
        )
        return result, evidence

    @staticmethod
    def _estimate_pair(image: np.ndarray, geometry: GaugeGeometry, calibration: GaugeCalibration, log: Any, pass_number: int) -> tuple[list[Measurement], list[str]]:
        estimates: list[NeedleEstimate] = []
        failures: list[str] = []
        for estimator, function in (("geometric", estimate_needle_geometric), ("polar", estimate_needle_polar)):
            try:
                estimate = function(image, geometry)
                estimates.append(estimate)
                log("MEASURING", f"estimate_needle_{estimator}", f"{estimator.capitalize()} estimator returned a candidate.", angle_deg=round(estimate.angle_deg, 3), pass_number=pass_number)
            except (NeedleNotFound, cv2.error) as exc:
                failures.append(f"{estimator.capitalize()} estimator: {str(exc)}")
                log("MEASURING", f"estimate_needle_{estimator}", f"{estimator.capitalize()} estimator found insufficient evidence.", pass_number=pass_number)
        measurements: list[Measurement] = []
        for estimate in estimates:
            calibrated = angle_to_value(estimate.angle_deg, calibration)
            if not isfinite(calibrated.value):
                failures.append(f"{estimate.estimator.capitalize()} estimate exceeded the supported numerical range.")
                continue
            measurements.append(Measurement(
                estimator=estimate.estimator,
                pass_number=pass_number,
                angle_deg=round(estimate.angle_deg, 3),
                value=calibrated.value,
                units=calibration.units,
                in_calibration_range=calibrated.in_range,
                evidence=estimate.evidence,
            ))
        return measurements, failures

    @staticmethod
    def compare_measurements(measurements: list[Measurement], calibration: GaugeCalibration) -> float:
        if len(measurements) < 2:
            return 100.0
        difference = measurements[0].value - measurements[1].value
        if not isfinite(difference):
            return 100.0  # Non-finite numerical evidence must fail the agreement gate.
        return abs(difference) / calibration.full_scale * 100.0

    @staticmethod
    def request_new_view(quality_reasons: tuple[str, ...]) -> str:
        if "localized_glare" in quality_reasons:
            return "Retake from a slightly different angle to move reflections off the dial, then keep the gauge centered."
        if "blur" in quality_reasons:
            return "Stabilize the camera and retake the image with the entire dial in focus."
        if "underexposure" in quality_reasons or "overexposure" in quality_reasons:
            return "Adjust exposure so the pointer and dial markings are both visible, then retake the image."
        if "estimator_disagreement" in quality_reasons:
            return "Capture one new view with the camera square to the dial and without reflections."
        return "Retake a sharp, unobstructed image with the complete dial visible."

    @staticmethod
    def escalate_to_human(reason: str) -> str:
        return f"Human review required: {reason}"
