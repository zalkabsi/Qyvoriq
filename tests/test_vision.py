import numpy as np
import pytest
from io import BytesIO
from PIL import Image

from backend.vision.estimators import NeedleNotFound, estimate_needle_geometric, estimate_needle_polar
from backend.vision.evidence import generate_evidence
from backend.vision.image_input import InvalidImage, decode_image
from backend.vision.localization import locate_gauge
from backend.vision.quality import assess_image_quality
from examples.synthetic import make_gauge


def test_image_validation_decodes_and_rejects_bad_content(encode_png, clear_image):
    encoded = encode_png(clear_image)
    decoded = decode_image(encoded)
    assert decoded.width == clear_image.shape[1]
    assert decoded.height == clear_image.shape[0]
    assert decoded.bgr.shape == clear_image.shape
    with pytest.raises(InvalidImage, match="could not be decoded"):
        decode_image(b"not an image")


def test_large_images_are_bounded_before_vision_and_orientation_is_preserved():
    output = BytesIO()
    Image.new("RGB", (2400, 1200), "white").save(output, format="PNG")
    decoded = decode_image(output.getvalue())
    assert (decoded.width, decoded.height) == (1600, 800)
    assert decoded.bgr.shape == (800, 1600, 3)
    output = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (400, 200), "white").save(output, format="JPEG", exif=exif)
    decoded = decode_image(output.getvalue())
    assert decoded.orientation_corrected
    assert (decoded.width, decoded.height) == (200, 400)


def test_elongated_images_fail_before_small_dimensions_reach_opencv():
    output = BytesIO()
    Image.new('RGB', (200, 5000), 'white').save(output, format='PNG')
    with pytest.raises(InvalidImage, match='too narrow'):
        decode_image(output.getvalue())


def test_quality_flags_glare_and_blur(clear_image):
    assert assess_image_quality(clear_image).usable
    glare = assess_image_quality(make_gauge(0.63, seed=17, glare=True).image)
    assert not glare.usable
    assert "localized_glare" in glare.reasons
    assert glare.glare_boxes
    blur = assess_image_quality(make_gauge(0.63, seed=17, blur=True).image)
    assert "blur" in blur.reasons


def test_localization_and_both_estimators_find_a_supported_pointer(clear_image):
    geometry = locate_gauge(clear_image)
    assert geometry is not None
    geometric = estimate_needle_geometric(clear_image, geometry)
    polar = estimate_needle_polar(clear_image, geometry)
    expected_angle = 135 + 0.63 * 270
    assert abs((geometric.angle_deg - expected_angle + 180) % 360 - 180) < 4
    assert abs((polar.angle_deg - expected_angle + 180) % 360 - 180) < 3


def test_missing_pointer_has_controlled_failure():
    import cv2

    image = np.full((640, 640, 3), 235, dtype=np.uint8)
    cv2.circle(image, (320, 320), 245, (30, 39, 45), 7, cv2.LINE_AA)
    cv2.circle(image, (320, 320), 236, (248, 249, 247), -1, cv2.LINE_AA)
    geometry = locate_gauge(image)
    assert geometry is not None
    with pytest.raises(NeedleNotFound):
        estimate_needle_geometric(image, geometry)
    with pytest.raises(NeedleNotFound):
        estimate_needle_polar(image, geometry)


def test_evidence_does_not_modify_original(clear_image):
    before = clear_image.copy()
    geometry = locate_gauge(clear_image)
    annotated = generate_evidence(clear_image, geometry, [], "VERIFIED")
    assert annotated.startswith(b"\x89PNG\r\n\x1a\n")
    assert np.array_equal(clear_image, before)
