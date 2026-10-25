from __future__ import annotations

import json
from pathlib import Path


POLICY_PATH = Path(__file__).with_name("policy.json")


def load_disagreement_limit(path: Path = POLICY_PATH) -> float:
    """Require the saved validation artifact instead of silently weakening its cap."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))["max_disagreement_pct_fs"]
        threshold = float(value)
        if 0.1 <= threshold <= 5.0:
            return threshold
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    raise RuntimeError("The validation-derived agreement policy is missing or invalid. Re-run policy calibration.")


MAX_DISAGREEMENT_PCT_FS = load_disagreement_limit()
