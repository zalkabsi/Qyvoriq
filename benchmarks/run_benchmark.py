from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.agents.orchestrator import MAX_DISAGREEMENT_PCT_FS, InspectionAgent
from backend.schemas import GaugeCalibration
from backend.vision.calibration import angle_to_value
from backend.vision.estimators import NeedleNotFound, estimate_needle_geometric, estimate_needle_polar
from backend.vision.localization import locate_gauge
from backend.vision.quality import assess_image_quality
from examples.synthetic import make_gauge


CALIBRATION = GaugeCalibration(
    minimum_value=0.0,
    maximum_value=100.0,
    units="psi",
    start_angle_deg=135.0,
    end_angle_deg=45.0,
    sweep_direction="clockwise",
)
SPLIT_OFFSETS = {"train": 0, "validation": 10_000, "test": 20_000}
CONDITIONS = ("clear", "glare", "blur", "noise")


def summarize(errors: list[float], sample_count: int, elapsed_ms: list[float]) -> dict[str, Any]:
    if errors:
        abs_errors = [abs(value) for value in errors]
        result: dict[str, Any] = {
            "predicted_count": len(errors),
            "coverage": round(len(errors) / sample_count, 4),
            "mae_fs_pct": round(statistics.mean(abs_errors), 4),
            "median_abs_error_fs_pct": round(statistics.median(abs_errors), 4),
            "p95_abs_error_fs_pct": round(float(np.percentile(abs_errors, 95)), 4),
            "accuracy_within_1pct_fs": round(sum(error <= 1.0 for error in abs_errors) / len(abs_errors), 4),
            "accuracy_within_2pct_fs": round(sum(error <= 2.0 for error in abs_errors) / len(abs_errors), 4),
            "accuracy_within_5pct_fs": round(sum(error <= 5.0 for error in abs_errors) / len(abs_errors), 4),
            "false_accept_rate_over_5pct_fs": round(sum(error > 5.0 for error in abs_errors) / len(abs_errors), 4),
        }
        count = sum(error > 5.0 for error in abs_errors)
        n, z = len(abs_errors), 1.9599639845
        proportion = count / n
        center = (proportion + z * z / (2 * n)) / (1 + z * z / n)
        half = z * float(np.sqrt(proportion * (1 - proportion) / n + z * z / (4 * n * n))) / (1 + z * z / n)
        result['false_accept_count_over_5pct_fs'] = count
        result['false_accept_wilson95_interval'] = [round(max(0, center - half), 6), round(min(1, center + half), 6)]
    else:
        result = {"predicted_count": 0, "coverage": 0.0, "mae_fs_pct": None, "median_abs_error_fs_pct": None, "p95_abs_error_fs_pct": None, "accuracy_within_1pct_fs": None, "accuracy_within_2pct_fs": None, "accuracy_within_5pct_fs": None, "false_accept_rate_over_5pct_fs": None}
    result["mean_latency_ms"] = round(statistics.mean(elapsed_ms), 3) if elapsed_ms else None
    result["p95_latency_ms"] = round(float(np.percentile(elapsed_ms, 95)), 3) if elapsed_ms else None
    result["throughput_images_per_second"] = round(1000.0 / statistics.mean(elapsed_ms), 3) if elapsed_ms and statistics.mean(elapsed_ms) else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate identical controlled synthetic images with three policies.")
    parser.add_argument("--split", choices=SPLIT_OFFSETS, default="test")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/latest.json"))
    args = parser.parse_args()
    if args.samples < 1 or args.samples > 5000:
        parser.error("--samples must be between 1 and 5000")

    agent = InspectionAgent()
    method_errors: dict[str, list[float]] = defaultdict(list)
    method_latencies: dict[str, list[float]] = defaultdict(list)
    raw_pairs: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)
    condition_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    agent_error_by_condition: dict[str, list[float]] = defaultdict(list)
    start_all = time.perf_counter()

    for index in range(args.samples):
        seed = args.seed + SPLIT_OFFSETS[args.split] + index
        rng = np.random.default_rng(seed)
        condition = CONDITIONS[index % len(CONDITIONS)]
        fraction = float(rng.uniform(0.06, 0.94))
        radius = int(rng.integers(215, 245))
        image = make_gauge(
            fraction,
            seed=seed,
            radius=radius,
            glare=condition == "glare",
            blur=condition == "blur",
            noise_std=6.0 if condition == "noise" else 0.0,
        ).image
        truth = fraction * CALIBRATION.full_scale
        method_start = time.perf_counter()
        geometry = locate_gauge(image)
        locate_ms = (time.perf_counter() - method_start) * 1000.0
        geometric_value: float | None = None
        polar_value: float | None = None
        geometric_ms = 0.0
        fusion_ms = 0.0
        quality = assess_image_quality(image)
        if geometry is not None:
            t0 = time.perf_counter()
            try:
                estimate = estimate_needle_geometric(image, geometry)
                reading = angle_to_value(estimate.angle_deg, CALIBRATION)
                geometric_value = reading.value
            except (NeedleNotFound, cv2.error):
                pass
            geometric_ms = (time.perf_counter() - t0) * 1000.0
            t0 = time.perf_counter()
            try:
                estimate = estimate_needle_polar(image, geometry)
                reading = angle_to_value(estimate.angle_deg, CALIBRATION)
                polar_value = reading.value
            except (NeedleNotFound, cv2.error):
                pass
            fusion_ms = (time.perf_counter() - t0) * 1000.0

        qyvoriq_start = time.perf_counter()
        result, _ = agent.inspect(f"synthetic-{args.split}-{index}", image, CALIBRATION)
        qyvoriq_ms = (time.perf_counter() - qyvoriq_start) * 1000.0

        predictions: dict[str, float | None] = {
            "baseline_a_geometric": geometric_value,
            "baseline_b_fixed_mean": (geometric_value + polar_value) / 2.0 if geometric_value is not None and polar_value is not None else None,
            "qyvoriq_selective": result.reading_value if result.state == "VERIFIED" else None,
        }
        disagreements: float | None = None
        if geometric_value is not None and polar_value is not None:
            disagreements = abs(geometric_value - polar_value) / CALIBRATION.full_scale * 100.0
            raw_pairs.append({"truth": truth, "geom": geometric_value, "polar": polar_value, "quality_usable": quality.usable,
                              "in_range": CALIBRATION.minimum_value <= geometric_value <= CALIBRATION.maximum_value and CALIBRATION.minimum_value <= polar_value <= CALIBRATION.maximum_value,
                              "disagreement": disagreements})
        status_counts[result.state] += 1
        condition_counts[condition]["samples"] += 1
        condition_counts[condition][result.state] += 1
        both_in_range = (
            geometric_value is not None and polar_value is not None
            and CALIBRATION.minimum_value <= geometric_value <= CALIBRATION.maximum_value
            and CALIBRATION.minimum_value <= polar_value <= CALIBRATION.maximum_value
        )
        row: dict[str, Any] = {
            "index": index,
            "seed": seed,
            "condition": condition,
            "ground_truth": round(truth, 6),
            "quality_usable": quality.usable,
            "both_estimators_in_calibration_range": both_in_range,
            "raw_estimator_readings": {"geometric": geometric_value, "polar": polar_value},
            "predictions": {},
            "state": result.state,
            "raw_estimator_disagreement_pct_fs": round(disagreements, 4) if disagreements is not None else None,
        }
        for method, prediction in predictions.items():
            if prediction is None:
                row["predictions"][method] = None
                continue
            error = (prediction - truth) / CALIBRATION.full_scale * 100.0
            method_errors[method].append(error)
            row["predictions"][method] = round(prediction, 6)
            if method == "qyvoriq_selective":
                agent_error_by_condition[condition].append(abs(error))
        method_latencies["baseline_a_geometric"].append(locate_ms + geometric_ms)
        method_latencies["baseline_b_fixed_mean"].append(locate_ms + geometric_ms + fusion_ms)
        method_latencies["qyvoriq_selective"].append(qyvoriq_ms)
        rows.append(row)

    sample_count = len(rows)
    summary = {name: summarize(errors, sample_count, method_latencies[name]) for name, errors in method_errors.items()}
    for name in ("baseline_a_geometric", "baseline_b_fixed_mean", "qyvoriq_selective"):
        summary.setdefault(name, summarize([], sample_count, method_latencies[name]))

    risk_curve: list[dict[str, float | int | None]] = []
    for threshold in sorted({1.0, 2.0, MAX_DISAGREEMENT_PCT_FS, 5.0, 7.5, 10.0, 100.0}):
        accepted = [row for row in raw_pairs if row["quality_usable"] and row["in_range"] and row["disagreement"] <= threshold]
        errors = [abs(((row["geom"] + row["polar"]) / 2.0 - row["truth"]) / CALIBRATION.full_scale * 100.0) for row in accepted]
        risk_curve.append({
            "disagreement_threshold_pct_fs": threshold,
            "accepted_count": len(accepted),
            "coverage": round(len(accepted) / sample_count, 4),
            "selective_mae_pct_fs": round(statistics.mean(errors), 4) if errors else None,
            "false_accept_rate_over_5pct_fs": round(sum(error > 5.0 for error in errors) / len(errors), 4) if errors else None,
        })

    condition_summary = {
        condition: {
            "sample_count": counts["samples"],
            "verified_count": counts.get("VERIFIED", 0),
            "reinspection_required_count": counts.get("REINSPECTION_REQUIRED", 0),
            "human_review_count": counts.get("HUMAN_REVIEW_REQUIRED", 0),
            "unsupported_count": counts.get("UNSUPPORTED_INSTRUMENT", 0),
            "agent_abstention_rate": round(1.0 - counts.get("VERIFIED", 0) / counts["samples"], 4),
            "agent_selective_mae_pct_fs": round(statistics.mean(agent_error_by_condition[condition]), 4) if agent_error_by_condition[condition] else None,
        }
        for condition, counts in condition_counts.items()
    }

    output: dict[str, Any] = {
        "schema_version": 1,
        "dataset": "Qyvoriq controlled synthetic gauge scenes",
        "dataset_type": "synthetic_only",
        "license": "CC0-1.0 for generated sample images; generator is covered by repository MIT license.",
        "split": args.split,
        "split_policy": "Disjoint deterministic seed ranges for train, validation, and test; the algorithm does not train on these images.",
        "samples": sample_count,
        "seed": args.seed + SPLIT_OFFSETS[args.split],
        "opencv_version": cv2.__version__,
        "calibration": CALIBRATION.model_dump(mode="json"),
        "policy": {"max_disagreement_pct_fs": MAX_DISAGREEMENT_PCT_FS, "false_accept_definition": "accepted reading with absolute error greater than 5% of full-scale span"},
        "runtime": {"total_seconds": round(time.perf_counter() - start_all, 3)},
        "summary": summary,
        "selective_risk_curve_fixed_mean": risk_curve,
        "failure_rate_by_condition": condition_summary,
        "agent_state_counts": dict(status_counts),
        "rows": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "samples": sample_count, "opencv_version": cv2.__version__, "summary": summary, "agent_state_counts": dict(status_counts)}, indent=2))


if __name__ == "__main__":
    main()
