from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class QualityAssessment:
    usable: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float]
    glare_boxes: tuple[tuple[int, int, int, int], ...]

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["glare_boxes"] = [list(box) for box in self.glare_boxes]
        return result


def assess_image_quality(image: np.ndarray) -> QualityAssessment:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_luminance = float(np.mean(gray))
    contrast = float(np.percentile(gray, 95) - np.percentile(gray, 5))
    clipped_bright_fraction = float(np.mean(gray >= 250))
    clipped_dark_fraction = float(np.mean(gray <= 5))

    # A compact, isolated saturated component is a glare cue. Broad white dial faces
    # are excluded by the upper area bound. This is a heuristic, not a confidence.
    bright_mask = cv2.inRange(gray, 251, 255)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(bright_mask, connectivity=8)
    image_area = image.shape[0] * image.shape[1]
    glare_boxes: list[tuple[int, int, int, int]] = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        fraction = area / image_area
        if 0.003 <= fraction <= 0.20 and w >= 12 and h >= 12:
            glare_boxes.append((x, y, w, h))

    reasons: list[str] = []
    if laplacian_variance < 35.0:
        reasons.append("blur")
    if mean_luminance < 35.0 or clipped_dark_fraction > 0.45:
        reasons.append("underexposure")
    if clipped_bright_fraction > 0.55:
        reasons.append("overexposure")
    if contrast < 28.0:
        reasons.append("low_contrast")
    if glare_boxes:
        reasons.append("localized_glare")

    return QualityAssessment(
        usable=not reasons,
        reasons=tuple(reasons),
        metrics={
            "laplacian_variance": round(laplacian_variance, 3),
            "mean_luminance": round(mean_luminance, 3),
            "contrast_p95_p5": round(contrast, 3),
            "clipped_bright_fraction": round(clipped_bright_fraction, 6),
            "clipped_dark_fraction": round(clipped_dark_fraction, 6),
        },
        glare_boxes=tuple(glare_boxes),
    )
