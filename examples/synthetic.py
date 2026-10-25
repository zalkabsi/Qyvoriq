from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

import cv2
import numpy as np


@dataclass(frozen=True)
class SyntheticGauge:
    image: np.ndarray
    reading: float
    fraction: float
    start_angle_deg: float = 135.0
    end_angle_deg: float = 45.0
    sweep_direction: str = "clockwise"
    units: str = "psi"


def make_gauge(
    fraction: float,
    *,
    seed: int = 0,
    glare: bool = False,
    blur: bool = False,
    second_pointer_fraction: float | None = None,
    noise_std: float = 0.0,
    radius: int = 236,
    image_size: int = 640,
    perturb_center: bool = True,
) -> SyntheticGauge:
    """Create a controllable synthetic dial for software checks, not field validation."""
    rng = np.random.default_rng(seed)
    fraction = float(np.clip(fraction, 0.0, 1.0))
    offset = rng.integers(-10, 11, size=2) if perturb_center else (0, 0)
    center = (image_size // 2 + int(offset[0]), image_size // 2 + int(offset[1]))
    canvas = np.full((image_size, image_size, 3), 235, dtype=np.uint8)
    cv2.circle(canvas, center, radius + 9, (30, 39, 45), thickness=7, lineType=cv2.LINE_AA)
    cv2.circle(canvas, center, radius, (226, 230, 229), thickness=-1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, center, radius - 2, (248, 249, 247), thickness=2, lineType=cv2.LINE_AA)

    start, span = 135.0, 270.0
    for index in range(41):
        position = index / 40.0
        angle = start + position * span
        length = 22 if index % 4 == 0 else 12
        outer = radius * 0.88
        inner = outer - length
        p1 = (round(center[0] + outer * cos(radians(angle))), round(center[1] + outer * sin(radians(angle))))
        p2 = (round(center[0] + inner * cos(radians(angle))), round(center[1] + inner * sin(radians(angle))))
        cv2.line(canvas, p1, p2, (48, 58, 63), 3 if index % 4 == 0 else 2, cv2.LINE_AA)

    cv2.putText(canvas, "PRESSURE", (center[0] - 66, center[1] + 116), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (72, 82, 84), 2, cv2.LINE_AA)
    cv2.putText(canvas, "psi", (center[0] - 15, center[1] + 146), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (94, 102, 103), 1, cv2.LINE_AA)

    def draw_pointer(at_fraction: float, color: tuple[int, int, int], width: int, pointer_radius: float) -> None:
        angle = start + float(at_fraction) * span
        tip = (round(center[0] + pointer_radius * cos(radians(angle))), round(center[1] + pointer_radius * sin(radians(angle))))
        base = (round(center[0] - 8 * cos(radians(angle))), round(center[1] - 8 * sin(radians(angle))))
        cv2.line(canvas, base, tip, (35, 42, 47), width + 2, cv2.LINE_AA)
        cv2.line(canvas, base, tip, color, width, cv2.LINE_AA)

    draw_pointer(fraction, (28, 59, 104), 6, radius * 0.72)
    if second_pointer_fraction is not None:
        draw_pointer(second_pointer_fraction, (54, 75, 94), 3, radius * 0.84)
    cv2.circle(canvas, center, 15, (30, 43, 51), thickness=-1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, center, 6, (171, 180, 177), thickness=-1, lineType=cv2.LINE_AA)

    if glare:
        # A localized saturated reflection on the glass, separate from the pale dial face.
        glare_center = (center[0] - round(radius * 0.27), center[1] - round(radius * 0.21))
        cv2.ellipse(canvas, glare_center, (54, 35), -24, 0, 360, (255, 255, 255), thickness=-1, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, glare_center, (64, 43), -24, 0, 360, (247, 249, 248), thickness=5, lineType=cv2.LINE_AA)
    if blur:
        canvas = cv2.GaussianBlur(canvas, (21, 21), 0)
    if noise_std > 0:
        noise = rng.normal(0.0, noise_std, canvas.shape).astype(np.float32)
        canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    value = fraction * 100.0
    return SyntheticGauge(canvas, value, fraction)
