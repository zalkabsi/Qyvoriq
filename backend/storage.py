from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

import numpy as np

from backend.schemas import GaugeCalibration, InspectionResult


TTL = timedelta(minutes=30)
MAX_INSPECTIONS = 100


@dataclass
class InspectionRecord:
    calibration: GaugeCalibration
    created_at: datetime
    updated_at: datetime
    attempt_number: int
    result: InspectionResult
    evidence_png: bytes
    latest_image: np.ndarray


class InMemoryInspectionStore:
    """Ephemeral demo store. No uploaded image is written to disk."""

    def __init__(self) -> None:
        self._records: dict[str, InspectionRecord] = {}
        self._lock = RLock()

    def _prune(self, now: datetime) -> None:
        expired = [key for key, record in self._records.items() if record.updated_at + TTL <= now]
        for key in expired:
            self._records.pop(key, None)
        if len(self._records) >= MAX_INSPECTIONS:
            oldest = min(self._records, key=lambda key: self._records[key].updated_at)
            self._records.pop(oldest, None)

    def create(self, key: str, record: InspectionRecord) -> None:
        with self._lock:
            self._prune(datetime.now(timezone.utc))
            self._records[key] = record

    def get(self, key: str) -> InspectionRecord | None:
        with self._lock:
            now = datetime.now(timezone.utc)
            record = self._records.get(key)
            if record is None or record.updated_at + TTL <= now:
                self._records.pop(key, None)
                return None
            return record

    def replace(self, key: str, record: InspectionRecord) -> None:
        with self._lock:
            self._records[key] = record
