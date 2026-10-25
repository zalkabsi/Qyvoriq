from __future__ import annotations

import hmac
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend.agents.orchestrator import MAX_FOLLOW_UPS, InspectionAgent, utc_now
from backend.schemas import GaugeCalibration
from backend.storage import InMemoryInspectionStore, InspectionRecord
from backend.vision.image_input import InvalidImage, decode_image


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(message)s")
logger = logging.getLogger("qyvoriq")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ID_PATTERN = re.compile(r"^[a-zA-Z0-9._:-]{1,80}$")
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"

store = InMemoryInspectionStore()
agent = InspectionAgent()
api_token = os.getenv("QYVORIQ_API_TOKEN", "")
environment = os.getenv("QYVORIQ_ENV", "development").lower()
if environment == "production" and not api_token:
    raise RuntimeError("QYVORIQ_API_TOKEN must be configured in production.")

origins = [origin.strip() for origin in os.getenv("QYVORIQ_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app = FastAPI(
    title="Qyvoriq Inspection API",
    version="0.1.0",
    docs_url=None if environment == "production" else "/docs",
    redoc_url=None if environment == "production" else "/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=False,
    max_age=600,
)


class RateLimiter:
    """Best-effort process-local limit; public deployments should also use AWS WAF."""

    def __init__(self) -> None:
        self.windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, key: tuple[str, str], limit: int, period: int = 60) -> bool:
        now = time.monotonic()
        window = self.windows[key]
        while window and window[0] <= now - period:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        if len(self.windows) > 5000:
            for old_key in tuple(self.windows):
                if not self.windows[old_key]:
                    self.windows.pop(old_key, None)
        return True


limiter = RateLimiter()


@app.middleware("http")
async def request_controls(request: Request, call_next: Any) -> Response:
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
    request.state.request_id = request_id
    path = request.url.path
    if path.startswith("/api/") and path not in {"/api/health/live", "/api/health/ready"}:
        client_ip = request.client.host if request.client else "unknown"
        group = "upload" if request.method == "POST" and path.endswith(("/inspections", "/images")) else "general"
        limit = 12 if group == "upload" else 120
        if not limiter.allow((client_ip, group), limit):
            response = JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Request limit reached. Try again shortly.", "request_id": request_id}})
            response.headers["X-Request-ID"] = request_id
            return response
        if api_token:
            authorization = request.headers.get("Authorization", "")
            expected = f"Bearer {api_token}"
            if not hmac.compare_digest(authorization, expected):
                response = JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "A valid inspection token is required.", "request_id": request_id}})
                response.headers["X-Request-ID"] = request_id
                response.headers["WWW-Authenticate"] = "Bearer"
                return response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({"event": "request_failed", "request_id": request_id, "path": path}))
        response = JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "The request could not be completed.", "request_id": request_id}})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    code = {404: "not_found", 409: "conflict", 413: "upload_too_large", 415: "unsupported_media_type", 422: "invalid_request"}.get(exc.status_code, "request_error")
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail), "request_id": request_id}})


async def read_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Use a JPEG, PNG, or WebP image.")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image upload exceeds the 10 MB limit.")
        chunks.append(chunk)
    if not total:
        raise HTTPException(422, "The uploaded file is empty.")
    return b"".join(chunks)


def parse_calibration(raw: str) -> GaugeCalibration:
    try:
        return GaugeCalibration.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(422, "Calibration is invalid: " + "; ".join(error["msg"] for error in exc.errors())) from exc


def read_inspection_or_404(inspection_id: str) -> InspectionRecord:
    try:
        # Reject malformed ids before they reach the store.
        from uuid import UUID

        UUID(inspection_id)
    except ValueError as exc:
        raise HTTPException(404, "Inspection was not found or has expired.") from exc
    record = store.get(inspection_id)
    if record is None:
        raise HTTPException(404, "Inspection was not found or has expired.")
    return record


@app.get("/api/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/api/health/ready")
def readiness() -> JSONResponse:
    opencv_ok = cv2.__version__.split(".", 1)[0] == "5"
    payload = {"status": "ready" if opencv_ok else "not_ready", "opencv_version": cv2.__version__, "opencv_major": cv2.__version__.split(".", 1)[0]}
    return JSONResponse(status_code=200 if opencv_ok else 503, content=payload)


@app.post("/api/inspections", status_code=201)
async def create_inspection(request: Request, file: UploadFile = File(...), calibration: str = Form(...)) -> dict[str, Any]:
    raw = await read_upload(file)
    await file.close()
    try:
        decoded = decode_image(raw)
    except InvalidImage as exc:
        raise HTTPException(422, str(exc)) from exc
    parsed_calibration = parse_calibration(calibration)
    inspection_id = str(uuid4())
    now = utc_now()
    result, evidence = agent.inspect(inspection_id, decoded.bgr, parsed_calibration, created_at=now)
    store.create(inspection_id, InspectionRecord(
        calibration=parsed_calibration,
        created_at=now,
        updated_at=now,
        attempt_number=0,
        result=result,
        evidence_png=evidence,
        latest_image=decoded.bgr,
    ))
    logger.info(json.dumps({"event": "inspection_created", "request_id": request.state.request_id, "inspection_id": inspection_id, "state": result.state, "attempt": 1, "opencv_version": cv2.__version__}))
    return result.model_dump(mode="json")


@app.get("/api/inspections/{inspection_id}")
def inspection_status(inspection_id: str) -> dict[str, object]:
    record = read_inspection_or_404(inspection_id)
    result = record.result
    return {
        "inspection_id": inspection_id,
        "state": result.state,
        "attempt_number": record.attempt_number + 1,
        "next_action": result.next_action,
        "created_at": result.created_at,
        "expires_at": result.expires_at,
    }


@app.get("/api/inspections/{inspection_id}/result")
def inspection_result(inspection_id: str) -> dict[str, Any]:
    record = read_inspection_or_404(inspection_id)
    return record.result.model_dump(mode="json")


@app.get("/api/inspections/{inspection_id}/evidence")
def inspection_evidence(inspection_id: str) -> Response:
    record = read_inspection_or_404(inspection_id)
    return Response(content=record.evidence_png, media_type="image/png", headers={"Content-Disposition": "inline; filename=inspection-evidence.png"})


@app.get("/api/benchmarks")
def benchmark_results() -> dict[str, Any]:
    path = ROOT / "benchmarks" / "results" / "latest.json"
    if not path.is_file():
        return {"available": False, "message": "Run `python -m benchmarks.run_benchmark` to generate measured synthetic results."}
    try:
        return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        raise HTTPException(503, "Benchmark results could not be loaded.")


@app.post("/api/inspections/{inspection_id}/images")
async def add_follow_up_image(request: Request, inspection_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    record = read_inspection_or_404(inspection_id)
    if record.result.state != "REINSPECTION_REQUIRED":
        raise HTTPException(409, "This inspection is not waiting for another image.")
    if record.attempt_number >= MAX_FOLLOW_UPS:
        raise HTTPException(409, "The maximum number of follow-up images has been reached.")
    raw = await read_upload(file)
    await file.close()
    try:
        decoded = decode_image(raw)
    except InvalidImage as exc:
        raise HTTPException(422, str(exc)) from exc
    attempt = record.attempt_number + 1
    now = utc_now()
    result, evidence = agent.inspect(
        inspection_id,
        decoded.bgr,
        record.calibration,
        attempt_number=attempt,
        prior_trace=record.result.trace,
        created_at=record.created_at,
    )
    record.attempt_number = attempt
    record.updated_at = now
    record.result = result
    record.evidence_png = evidence
    record.latest_image = decoded.bgr
    store.replace(inspection_id, record)
    logger.info(json.dumps({"event": "inspection_reobserved", "request_id": request.state.request_id, "inspection_id": inspection_id, "state": result.state, "attempt": attempt + 1, "opencv_version": cv2.__version__}))
    return result.model_dump(mode="json")


@app.get("/", include_in_schema=False)
def frontend() -> Response:
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"service": "Qyvoriq", "message": "Build the frontend with `npm --prefix frontend run build`.", "health": "/api/health/ready"})


if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")
if (FRONTEND_DIST / "scenarios").is_dir():
    app.mount("/scenarios", StaticFiles(directory=FRONTEND_DIST / "scenarios"), name="scenario-assets")
