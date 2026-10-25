from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from backend.schemas import GaugeCalibration, InspectionResult


TTL = timedelta(minutes=30)
MAX_INSPECTIONS = 100
MAX_EVIDENCE_BYTES = 128 * 1024 * 1024


@dataclass
class InspectionRecord:
    calibration: GaugeCalibration
    created_at: datetime
    updated_at: datetime
    attempt_number: int
    result: InspectionResult
    evidence_png: bytes


class InMemoryInspectionStore:
    """Bounded evidence store; source pixels are discarded after analysis."""

    def __init__(self, max_inspections: int = MAX_INSPECTIONS, max_evidence_bytes: int = MAX_EVIDENCE_BYTES) -> None:
        self._records: dict[str, InspectionRecord] = {}
        self._lock = RLock()
        self.max_inspections = max_inspections
        self.max_evidence_bytes = max_evidence_bytes

    def _prune(self, now: datetime) -> None:
        expired = [key for key, record in self._records.items() if record.updated_at + TTL <= now]
        for key in expired:
            self._records.pop(key, None)
        while self._records and (
            len(self._records) > self.max_inspections
            or sum(len(record.evidence_png) for record in self._records.values()) > self.max_evidence_bytes
        ):
            oldest = min(self._records, key=lambda key: self._records[key].updated_at)
            self._records.pop(oldest, None)

    def purge_expired(self) -> None:
        with self._lock:
            self._prune(datetime.now(timezone.utc))

    def create(self, key: str, record: InspectionRecord) -> None:
        with self._lock:
            if len(record.evidence_png) > self.max_evidence_bytes:
                raise ValueError("A single evidence image exceeds the store's byte budget.")
            self._records[key] = record
            self._prune(datetime.now(timezone.utc))

    def get(self, key: str) -> InspectionRecord | None:
        with self._lock:
            now = datetime.now(timezone.utc)
            self._prune(now)
            record = self._records.get(key)
            if record is None or record.updated_at + TTL <= now:
                self._records.pop(key, None)
                return None
            return record

    def replace(self, key: str, record: InspectionRecord) -> None:
        self.create(key, record)
