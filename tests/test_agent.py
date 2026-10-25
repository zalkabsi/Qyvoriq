from backend.agents.orchestrator import InspectionAgent
from examples.synthetic import make_gauge
from pathlib import Path

import cv2


def test_clear_observation_is_accepted_under_policy(calibration):
    result, evidence = InspectionAgent().inspect("clear-test", make_gauge(0.63, seed=17).image, calibration)
    assert result.state == "VERIFIED"
    assert result.reading_value is not None
    assert abs(result.reading_value - 63.0) < 2.0
    assert len(result.measurements) == 2
    tools = [event.tool for event in result.trace]
    assert "estimate_needle_geometric" in tools
    assert "estimate_needle_polar" in tools
    assert "compare_measurements" in tools
    assert "generate_evidence" in tools
    assert evidence.startswith(b"\x89PNG\r\n\x1a\n")


def test_glare_changes_the_next_action_and_skips_estimators(calibration):
    result, _ = InspectionAgent().inspect("glare-test", make_gauge(0.63, seed=17, glare=True).image, calibration)
    assert result.state == "REINSPECTION_REQUIRED"
    assert result.next_action
    tools = [event.tool for event in result.trace]
    assert "request_new_view" in tools
    assert "estimate_needle_geometric" not in tools
    assert "estimate_needle_polar" not in tools


def test_bad_quality_escalates_after_bounded_followups(calibration):
    result, _ = InspectionAgent().inspect("blur-retry-limit", make_gauge(0.63, seed=17, blur=True).image, calibration, attempt_number=2)
    assert result.state == "HUMAN_REVIEW_REQUIRED"
    assert "escalate_to_human" in [event.tool for event in result.trace]


def test_unsupported_rectangular_meter_is_declined(calibration):
    image_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "scenarios" / "unsupported.png"
    image = cv2.imread(str(image_path))
    assert image is not None
    result, _ = InspectionAgent().inspect("unsupported-test", image, calibration)
    assert result.state == "UNSUPPORTED_INSTRUMENT"
    assert result.reading_value is None
