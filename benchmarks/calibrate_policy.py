from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


MINIMUM_VALIDATION_SAMPLES = 20
TARGET_RETAINED_COVERAGE = 0.95
MAX_THRESHOLD_PCT_FS = 5.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit the estimator agreement threshold from a validation-only benchmark output.")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    payload: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("split") != "validation":
        parser.error("Calibration accepts only benchmark outputs tagged split=validation.")
    if payload.get("dataset_type") != "synthetic_only":
        parser.error("This implementation only supports explicit synthetic validation data.")

    eligible: list[dict[str, Any]] = []
    evaluatable: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        disagreement = row.get("raw_estimator_disagreement_pct_fs")
        fixed_mean = row.get("predictions", {}).get("baseline_b_fixed_mean")
        if not row.get("quality_usable") or not row.get("both_estimators_in_calibration_range"):
            continue
        if disagreement is None or fixed_mean is None:
            continue
        error_pct_fs = abs(float(fixed_mean) - float(row["ground_truth"]))
        candidate = {"disagreement": float(disagreement), "error_pct_fs": error_pct_fs, "seed": row.get("seed")}
        evaluatable.append(candidate)
        if error_pct_fs <= 2.0:
            eligible.append(candidate)
    if len(eligible) < MINIMUM_VALIDATION_SAMPLES:
        parser.error(f"Need at least {MINIMUM_VALIDATION_SAMPLES} usable validation examples; found {len(eligible)}.")

    # Choose the narrowest agreement cap that retains at least 95% of validation
    # pairs whose fixed-mean reading is within 2% FS. The test split is never read.
    disagreements = np.asarray([item["disagreement"] for item in eligible], dtype=float)
    threshold = float(np.quantile(disagreements, TARGET_RETAINED_COVERAGE, method="higher"))
    threshold = min(MAX_THRESHOLD_PCT_FS, max(0.1, threshold))
    retained = [item for item in eligible if item["disagreement"] <= threshold]
    high_error = [item for item in evaluatable if item["error_pct_fs"] > 5.0]
    artifact = {
        "policy_id": "synthetic-validation-v1",
        "max_disagreement_pct_fs": round(threshold, 3),
        "fit_method": "95th percentile (higher quantile) of raw estimator disagreement among quality-usable, in-range validation pairs with fixed-mean absolute error <= 2% of full-scale span",
        "target_retained_coverage": TARGET_RETAINED_COVERAGE,
        "validation_source": str(args.input),
        "validation_samples_total": int(payload["samples"]),
        "validation_eligible_pairs": len(eligible),
        "validation_retained_pairs": len(retained),
        "validation_retained_fraction": round(len(retained) / len(eligible), 4),
        "validation_pairs_over_5pct_fs": len(high_error),
        "validation_false_accept_count_over_5pct_fs": sum(item["disagreement"] <= threshold for item in high_error),
        "caveat": "Fit only to generated synthetic scenes. This threshold has no established calibration on SyncG or real photographs.",
        "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    repo = Path(__file__).resolve().parents[1]
    policy_path = repo / "backend" / "agents" / "policy.json"
    result_path = repo / "benchmarks" / "results" / "policy-calibration.json"
    policy_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    result_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
