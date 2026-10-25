from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_PIXELS = 16_000_000
MAX_WORKING_EDGE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImage(ValueError):
    """Raised when an uploaded image is malformed or outside supported bounds."""


@dataclass(frozen=True)
class DecodedImage:
    bgr: np.ndarray
    width: int
    height: int
    format: str
    orientation_corrected: bool


def decode_image(data: bytes) -> DecodedImage:
    if not data:
        raise InvalidImage("The uploaded file is empty.")
    try:
        with Image.open(BytesIO(data)) as opened:
            if opened.format not in ALLOWED_FORMATS:
                raise InvalidImage("Use a JPEG, PNG, or WebP image.")
            width, height = opened.size
            if width < 160 or height < 160:
                raise InvalidImage("Image dimensions must be at least 160 by 160 pixels.")
            if width * height > MAX_PIXELS:
                raise InvalidImage("Image resolution exceeds the 16 megapixel limit.")
            orientation = opened.getexif().get(274)
            corrected = orientation not in (None, 1)
            oriented = ImageOps.exif_transpose(opened).convert("RGB")
            oriented.thumbnail((MAX_WORKING_EDGE, MAX_WORKING_EDGE), Image.Resampling.LANCZOS)
            width, height = oriented.size
            if min(width, height) < 160:
                raise InvalidImage("The image is too narrow after normalization; include the complete dial in a less elongated frame.")
            rgb = np.asarray(oriented)
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("The image could not be decoded safely.") from exc
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise InvalidImage("Image must decode to 8-bit RGB color.")
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if bgr.shape[0] != height or bgr.shape[1] != width:
        height, width = bgr.shape[:2]
    return DecodedImage(bgr=bgr, width=width, height=height, format="JPEG" if opened.format == "JPG" else opened.format, orientation_corrected=corrected)
