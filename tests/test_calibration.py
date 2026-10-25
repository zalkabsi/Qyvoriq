from backend.schemas import GaugeCalibration
from backend.vision.calibration import angle_to_value
import pytest


def test_clockwise_wraparound_and_midpoint(calibration):
    assert angle_to_value(135, calibration).value == 0
    assert abs(angle_to_value(270, calibration).value - 50) < 1e-9
    assert angle_to_value(45, calibration).value == 100


def test_counterclockwise_wraparound():
    calibration = GaugeCalibration(
        minimum_value=-20,
        maximum_value=80,
        units="kPa",
        start_angle_deg=225,
        end_angle_deg=315,
        sweep_direction="counterclockwise",
    )
    reading = angle_to_value(90, calibration)
    assert reading.in_range
    assert abs(reading.value - 30) < 1e-9


def test_out_of_range_angle_is_not_silently_clamped(calibration):
    reading = angle_to_value(60, calibration)
    assert not reading.in_range
    assert reading.value > calibration.maximum_value


def test_invalid_scale_and_sweep_are_rejected():
    try:
        GaugeCalibration(minimum_value=2, maximum_value=2, units="x", start_angle_deg=0, end_angle_deg=90, sweep_direction="clockwise")
    except ValueError:
        pass
    else:
        raise AssertionError("equal scale endpoints must be invalid")
    try:
        GaugeCalibration(minimum_value=0, maximum_value=1, units="x", start_angle_deg=0, end_angle_deg=10, sweep_direction="clockwise")
    except ValueError:
        pass
    else:
        raise AssertionError("a sweep under 20 degrees must be invalid")


@pytest.mark.parametrize("minimum,maximum", [(0, float("nan")), (0, float("inf")), (-float("inf"), 1), (-1e308, 1e308)])
def test_nonfinite_calibration_cannot_reach_vision(minimum, maximum):
    with pytest.raises(ValueError):
        GaugeCalibration(minimum_value=minimum, maximum_value=maximum, units="psi", start_angle_deg=135, end_angle_deg=45, sweep_direction="clockwise")
