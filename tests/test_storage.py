from datetime import datetime, timedelta, timezone

from backend.agents.orchestrator import InspectionAgent
from backend.storage import InMemoryInspectionStore, InspectionRecord


def record(calibration, clear_image, when, size=6):
    result, _ = InspectionAgent().inspect('memory-check', clear_image, calibration)
    return InspectionRecord(calibration, when, when, 0, result, b'x' * size)


def test_evidence_budget_evicts_oldest_record(calibration, clear_image):
    store = InMemoryInspectionStore(max_evidence_bytes=10)
    now = datetime.now(timezone.utc)
    store.create('old', record(calibration, clear_image, now - timedelta(seconds=2)))
    store.create('new', record(calibration, clear_image, now))
    assert store.get('old') is None
    assert store.get('new') is not None


def test_expired_evidence_is_purged_without_a_new_upload(calibration, clear_image):
    store = InMemoryInspectionStore()
    now = datetime.now(timezone.utc)
    item = record(calibration, clear_image, now)
    store.create('inspection', item)
    item.updated_at = now - timedelta(minutes=31)
    store.purge_expired()
    assert store.get('inspection') is None
    assert not store._records
