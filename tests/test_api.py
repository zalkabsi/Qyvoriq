import json

from fastapi.testclient import TestClient

from backend.api import app, limiter, store
from examples.synthetic import make_gauge


def setup_function():
    limiter.windows.clear()
    with store._lock:
        store._records.clear()


def payload(file_bytes: bytes, name: str = "gauge.png"):
    calibration = {
        "minimum_value": 0,
        "maximum_value": 100,
        "units": "psi",
        "start_angle_deg": 135,
        "end_angle_deg": 45,
        "sweep_direction": "clockwise",
    }
    return {"files": {"file": (name, file_bytes, "image/png")}, "data": {"calibration": json.dumps(calibration)}}


def test_health_ready_reports_actual_opencv_major():
    with TestClient(app) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json()["opencv_major"] == "5"


def test_create_status_result_and_evidence(encode_png, clear_image):
    with TestClient(app) as client:
        created = client.post("/api/inspections", **payload(encode_png(clear_image)))
        assert created.status_code == 201
        result = created.json()
        inspection_id = result["inspection_id"]
        assert result["state"] == "VERIFIED"
        assert result["reading_value"] is not None
        assert created.headers.get("x-request-id")
        status = client.get(f"/api/inspections/{inspection_id}")
        full_result = client.get(f"/api/inspections/{inspection_id}/result")
        evidence = client.get(f"/api/inspections/{inspection_id}/evidence")
    assert status.status_code == 200
    assert status.json()["state"] == "VERIFIED"
    assert full_result.json()["trace"]
    assert evidence.status_code == 200
    assert evidence.headers["content-type"] == "image/png"


def test_real_followup_image_resolves_a_glare_request(encode_png):
    glare = make_gauge(0.63, seed=17, glare=True).image
    clear = make_gauge(0.63, seed=17).image
    with TestClient(app) as client:
        created = client.post("/api/inspections", **payload(encode_png(glare)))
        assert created.status_code == 201
        first = created.json()
        assert first["state"] == "REINSPECTION_REQUIRED"
        continued = client.post(
            f"/api/inspections/{first['inspection_id']}/images",
            files={"file": ("second-view.png", encode_png(clear), "image/png")},
        )
    assert continued.status_code == 200
    assert continued.json()["state"] == "VERIFIED"
    assert continued.json()["attempt_number"] == 2
    assert any(event["tool"] == "reinspect_image" for event in continued.json()["trace"])


def test_upload_limits_and_missing_inspection_are_controlled():
    with TestClient(app) as client:
        unsupported = client.post("/api/inspections", files={"file": ("x.gif", b"x", "image/gif")}, data={"calibration": "{}"})
        missing = client.get("/api/inspections/not-an-id")
    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "unsupported_media_type"
    assert missing.status_code == 404
