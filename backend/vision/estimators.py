from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot

import cv2
import numpy as np

from backend.vision.localization import GaugeGeometry


@dataclass(frozen=True)
class NeedleEstimate:
    estimator: str
    angle_deg: float
    evidence: dict[str, float | int | str]


class NeedleNotFound(ValueError):
    pass


def _screen_angle(cx: float, cy: float, x: float, y: float) -> float:
    return degrees(atan2(y - cy, x - cx)) % 360.0


def estimate_needle_geometric(image: np.ndarray, geometry: GaugeGeometry) -> NeedleEstimate:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.0)
    edges = cv2.Canny(gray, 40, 120)
    min_length = max(24, int(geometry.radius * 0.25))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=max(18, int(geometry.radius * 0.12)),
        minLineLength=min_length,
        maxLineGap=max(5, int(geometry.radius * 0.035)),
    )
    if lines is None:
        raise NeedleNotFound("No radial line evidence was detected.")

    cx, cy, radius = geometry.center_x, geometry.center_y, geometry.radius
    candidates: list[tuple[float, float, float, float]] = []
    for line in np.asarray(lines).reshape(-1, 4):
        x1, y1, x2, y2 = (float(value) for value in line)
        vx, vy = x2 - x1, y2 - y1
        length = hypot(vx, vy)
        if length < min_length:
            continue
        distance = abs(vx * (y1 - cy) - (x1 - cx) * vy) / max(length, 1e-6)
        if distance > radius * 0.075:
            continue
        d1, d2 = hypot(x1 - cx, y1 - cy), hypot(x2 - cx, y2 - cy)
        near, far = sorted((d1, d2))
        if near > radius * 0.30 or far < radius * 0.40 or far > radius * 1.03:
            continue
        radial_length = far - near
        if radial_length < radius * 0.24:
            continue
        score = (radial_length / radius) * max(0.0, 1.0 - distance / (radius * 0.08))
        tip_x, tip_y = (x1, y1) if d1 >= d2 else (x2, y2)
        candidates.append((score, _screen_angle(cx, cy, tip_x, tip_y), radial_length, distance))

    if not candidates:
        raise NeedleNotFound("No line passed the needle-origin and radial-length checks.")
    score, angle, length, distance = max(candidates, key=lambda item: item[0])
    return NeedleEstimate(
        estimator="geometric",
        angle_deg=angle,
        evidence={"line_length_px": round(length, 2), "center_offset_px": round(distance, 2), "candidate_count": len(candidates)},
    )


def estimate_needle_polar(image: np.ndarray, geometry: GaugeGeometry) -> NeedleEstimate:
    """Find a radial dark-line response after OpenCV's linear polar transform."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    radius = max(32, int(geometry.radius))
    polar = cv2.warpPolar(
        gray,
        (radius, 360),
        (float(geometry.center_x), float(geometry.center_y)),
        float(geometry.radius),
        cv2.WARP_POLAR_LINEAR | cv2.WARP_FILL_OUTLIERS,
    )
    inner, outer = max(8, int(radius * 0.23)), max(10, int(radius * 0.82))
    band = polar[:, inner:outer].astype(np.float32)
    if band.shape[1] < 16:
        raise NeedleNotFound("Gauge radius is too small for polar analysis.")
    local_reference = np.median(band, axis=0, keepdims=True)
    dark_response = np.maximum(local_reference - band, 0.0)
    angular_response = np.mean(dark_response, axis=1)
    angular_response = cv2.GaussianBlur(angular_response.reshape(-1, 1), (1, 5), 0).reshape(-1)
    peak = int(np.argmax(angular_response))
    peak_value = float(angular_response[peak])
    if peak_value < 4.0:
        raise NeedleNotFound("Polar transform did not contain a distinct radial pointer response.")
    # warpPolar's angular coordinate follows image coordinates: 0 degrees points right,
    # increasing angles move clockwise because image y increases downward.
    return NeedleEstimate(
        estimator="polar",
        angle_deg=float(peak % 360),
        evidence={"polar_response": round(peak_value, 3), "radial_samples": int(band.shape[1]), "angular_bins": 360},
    )


def reinspect_image(image: np.ndarray) -> np.ndarray:
    """Return a contrast-normalized working copy for one bounded second pass."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)
    normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((normalized, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
