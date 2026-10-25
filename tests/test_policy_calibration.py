import json
import subprocess
import sys
from pathlib import Path
import pytest

from backend.agents.policy import load_disagreement_limit


def test_validation_fit_uses_full_scale_error_after_unit_conversion(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / 'benchmarks/results/validation.json').read_text())
    expected = json.loads((root / 'backend/agents/policy.json').read_text())
    source['calibration']['maximum_value'] *= 100
    for row in source['rows']:
        row['ground_truth'] *= 100
        for name, prediction in row['predictions'].items():
            if prediction is not None:
                row['predictions'][name] *= 100
    path = tmp_path / 'different-units.json'
    path.write_text(json.dumps(source))
    completed = subprocess.run([sys.executable, '-m', 'benchmarks.calibrate_policy', '--input', str(path), '--dry-run'], cwd=root, check=True, capture_output=True, text=True)
    fitted = json.loads(completed.stdout)
    assert fitted['validation_eligible_pairs'] == expected['validation_eligible_pairs']
    assert fitted['max_disagreement_pct_fs'] == expected['max_disagreement_pct_fs']


@pytest.mark.parametrize('value', [None, 'broken', 9, float('nan')])
def test_bad_saved_policy_cannot_silently_weaken_acceptance(tmp_path, value):
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps({'max_disagreement_pct_fs': value}))
    with pytest.raises(RuntimeError, match='missing or invalid'):
        load_disagreement_limit(path)


def test_missing_saved_policy_prevents_startup(tmp_path):
    with pytest.raises(RuntimeError, match='missing or invalid'):
        load_disagreement_limit(tmp_path / 'absent.json')
