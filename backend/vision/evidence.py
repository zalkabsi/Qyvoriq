from __future__ import annotations

import base64

import cv2
import numpy as np

from backend.vision.localization import GaugeGeometry


def generate_evidence(
    original: np.ndarray,
    geometry: GaugeGeometry | None,
    measurements: list[dict[str, object]],
    status: str,
    glare_boxes: list[list[int]] | None = None,
) -> bytes:
    """Draw measurement geometry on a copy; the uploaded pixels stay untouched."""
    annotated = original.copy()
    if geometry is not None:
        center = (round(geometry.center_x), round(geometry.center_y))
        cv2.circle(annotated, center, round(geometry.radius), (20, 180, 132), 2, cv2.LINE_AA)
        cv2.circle(annotated, center, 5, (40, 120, 255), -1, cv2.LINE_AA)
        cv2.putText(annotated, "rotation center", (center[0] + 9, center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (40, 120, 255), 1, cv2.LINE_AA)
        colors = {"geometric": (35, 160, 255), "polar": (255, 175, 35)}
        for item in measurements:
            angle = float(item["angle_deg"])
            length = geometry.radius * 0.78
            endpoint = (
                round(geometry.center_x + length * np.cos(np.deg2rad(angle))),
                round(geometry.center_y + length * np.sin(np.deg2rad(angle))),
            )
            cv2.line(annotated, center, endpoint, colors.get(str(item.get("estimator")), (255, 255, 0)), 2, cv2.LINE_AA)
    for box in glare_boxes or []:
        if len(box) == 4:
            x, y, w, h = (int(v) for v in box)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 190, 255), 2, cv2.LINE_AA)
    overlay = annotated.copy()
    cv2.rectangle(overlay, (0, 0), (annotated.shape[1], 46), (15, 30, 43), thickness=-1)
    cv2.addWeighted(overlay, 0.82, annotated, 0.18, 0, annotated)
    cv2.putText(annotated, f"QYVORIQ  |  {status.replace('_', ' ')}", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 248, 250), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".png", annotated, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise RuntimeError("OpenCV could not encode the evidence image.")
    return encoded.tobytes()


def evidence_data_url(image_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
