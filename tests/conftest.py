from __future__ import annotations

import cv2
import pytest

from backend.schemas import GaugeCalibration
from examples.synthetic import make_gauge


@pytest.fixture
def calibration() -> GaugeCalibration:
    return GaugeCalibration(
        minimum_value=0,
        maximum_value=100,
        units="psi",
        start_angle_deg=135,
        end_angle_deg=45,
        sweep_direction="clockwise",
    )


@pytest.fixture
def clear_image():
    return make_gauge(0.63, seed=17).image


@pytest.fixture
def encode_png():
    def encode(image):
        ok, encoded = cv2.imencode(".png", image)
        assert ok
        return encoded.tobytes()
    return encode
