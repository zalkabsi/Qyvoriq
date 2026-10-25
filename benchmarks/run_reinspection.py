"""A controlled paired-observation test; this is not a physical camera study."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from backend.agents.orchestrator import InspectionAgent
from benchmarks.run_benchmark import CALIBRATION
from examples.synthetic import make_gauge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--output', type=Path, default=Path('benchmarks/results/reinspection.json'))
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        parser.error('--samples must be between 1 and 1000')
    agent = InspectionAgent()
    rows = []
    for index in range(args.samples):
        seed = 42_026 + index
        fraction = float(np.random.default_rng(seed).uniform(0.10, 0.90))
        truth = CALIBRATION.minimum_value + fraction * CALIBRATION.full_scale
        glare = make_gauge(fraction, seed=seed, glare=True).image
        clear = make_gauge(fraction, seed=seed).image
        first, _ = agent.inspect(f'paired-{seed}', glare, CALIBRATION)
        second, _ = agent.inspect(f'paired-{seed}', clear, CALIBRATION, attempt_number=1, prior_trace=first.trace)
        persistent, _ = agent.inspect(f'persistent-{seed}', glare, CALIBRATION, attempt_number=2, prior_trace=first.trace)
        error = abs(second.reading_value - truth) / CALIBRATION.full_scale * 100 if second.reading_value is not None else None
        rows.append({
            'seed': seed, 'ground_truth': truth,
            'first_state': first.state,
            'first_skipped_estimators': not any(event.tool.startswith('estimate_needle_') for event in first.trace),
            'follow_up_state': second.state,
            'follow_up_reading': second.reading_value,
            'follow_up_error_pct_fs': error,
            'successful_follow_up_within_2pct_fs': second.state == 'VERIFIED' and error is not None and error <= 2.0,
            'persistent_glare_state_at_retry_limit': persistent.state,
        })
    requested = sum(row['first_state'] == 'REINSPECTION_REQUIRED' for row in rows)
    accepted = sum(row['follow_up_state'] == 'VERIFIED' for row in rows)
    success = sum(row['successful_follow_up_within_2pct_fs'] for row in rows)
    escalated = sum(row['persistent_glare_state_at_retry_limit'] == 'HUMAN_REVIEW_REQUIRED' for row in rows)
    artifact = {
        'dataset_type': 'controlled_synthetic_paired_observations',
        'description': 'For each seed, the same rendered dial and stable reading are observed with localized glare and without glare. No camera pose changes or real photographs are involved.',
        'samples': len(rows), 'seed_start': 42_026,
        'opencv_version': cv2.__version__, 'calibration': CALIBRATION.model_dump(mode='json'),
        'first_image_reinspection_requests': requested,
        'first_image_estimator_skip_count': sum(row['first_skipped_estimators'] for row in rows),
        'follow_up_verified_count': accepted,
        'follow_up_success_within_2pct_fs_count': success,
        'follow_up_success_rate': success / requested if requested else None,
        'false_accept_over_5pct_fs_count': sum(row['follow_up_state'] == 'VERIFIED' and row['follow_up_error_pct_fs'] > 5 for row in rows),
        'persistent_glare_human_escalation_count': escalated,
        'limitation': 'Controlled workflow evidence only. This does not estimate a physical retake success rate or performance on real gauges.',
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'rows': rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in artifact.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
