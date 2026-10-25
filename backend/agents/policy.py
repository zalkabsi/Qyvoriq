from __future__ import annotations

import json
from pathlib import Path


POLICY_PATH = Path(__file__).with_name("policy.json")
DEFAULT_MAX_DISAGREEMENT_PCT_FS = 3.5


def load_disagreement_limit() -> float:
    """Load the validation-fitted threshold; keep a conservative local fallback."""
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))["max_disagreement_pct_fs"]
        threshold = float(value)
        if 0.1 <= threshold <= 5.0:
            return threshold
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return DEFAULT_MAX_DISAGREEMENT_PCT_FS


MAX_DISAGREEMENT_PCT_FS = load_disagreement_limit()
