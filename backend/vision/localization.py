from __future__ import annotations

from dataclasses import dataclass
from math import hypot

import cv2
import numpy as np


@dataclass(frozen=True)
class GaugeGeometry:
    center_x: float
    center_y: float
    radius: float
    boundary_support: float
    method: str

    def as_dict(self) -> dict[str, float | str]:
        return {
            "center_x": round(self.center_x, 2),
            "center_y": round(self.center_y, 2),
            "radius_px": round(self.radius, 2),
            "boundary_support": round(self.boundary_support, 4),
            "method": self.method,
        }


def _circle_support(edges: np.ndarray, cx: float, cy: float, radius: float) -> float:
    canvas = np.zeros_like(edges)
    cv2.circle(canvas, (round(cx), round(cy)), round(radius), 255, thickness=1, lineType=cv2.LINE_8)
    band = cv2.dilate(canvas, np.ones((7, 7), np.uint8)) > 0
    return float(np.count_nonzero((edges > 0) & band) / max(1, np.count_nonzero(band)))


def locate_gauge(image: np.ndarray) -> GaugeGeometry | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    height, width = gray.shape
    min_dim = min(height, width)
    edges = cv2.Canny(gray, 45, 130)
    candidates: list[tuple[float, float, float, float, str]] = []

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(40, int(min_dim * 0.25)),
        param1=110,
        param2=42,
        minRadius=max(50, int(min_dim * 0.20)),
        maxRadius=int(min_dim * 0.48),
    )
    if circles is not None:
        for cx, cy, radius in circles[0]:
            if cx - radius < 2 or cy - radius < 2 or cx + radius > width - 2 or cy + radius > height - 2:
                continue
            support = _circle_support(edges, float(cx), float(cy), float(radius))
            center_distance = hypot(cx - width / 2.0, cy - height / 2.0) / min_dim
            center_prior = max(0.0, 1.0 - center_distance / 0.70)
            score = 0.75 * support + 0.25 * center_prior
            candidates.append((score, float(cx), float(cy), float(radius), "hough_circle"))

    # Contours are a fallback when a partial but coherent dial boundary defeats Hough.
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < (min_dim * 0.18) ** 2:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
        # A square's contour circularity is about 0.785; keep a stricter floor so
        # rectangular instruments are not accepted by the enclosing-circle fallback.
        if circularity < 0.82:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        if not min_dim * 0.20 <= radius <= min_dim * 0.48:
            continue
        if cx - radius < 2 or cy - radius < 2 or cx + radius > width - 2 or cy + radius > height - 2:
            continue
        support = _circle_support(edges, cx, cy, radius)
        center_distance = hypot(cx - width / 2.0, cy - height / 2.0) / min_dim
        center_prior = max(0.0, 1.0 - center_distance / 0.70)
        score = 0.75 * support + 0.25 * center_prior
        candidates.append((score, float(cx), float(cy), float(radius), "circular_contour"))

    if not candidates:
        return None
    score, cx, cy, radius, method = max(candidates, key=lambda item: item[0])
    if score < 0.12:
        return None
    return GaugeGeometry(cx, cy, radius, min(1.0, score), method)
