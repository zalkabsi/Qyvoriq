from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from backend.agents.orchestrator import InspectionAgent
from backend.schemas import GaugeCalibration
from examples import synthetic  # noqa: F401
from scripts.generate_scenarios import main as generate_scenarios


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "frontend" / "public" / "scenarios"
OUTPUT = ROOT / "examples" / "scenarios" / "actual_outputs.json"
CALIBRATION = GaugeCalibration(
    minimum_value=0,
    maximum_value=100,
    units="psi",
    start_angle_deg=135,
    end_angle_deg=45,
    sweep_direction="clockwise",
)


def main() -> None:
    generate_scenarios()
    manifest: dict[str, Any] = json.loads((SCENARIO_DIR / "manifest.json").read_text(encoding="utf-8"))
    agent = InspectionAgent()
    scenarios: list[dict[str, Any]] = []
    for entry in manifest["scenarios"]:
        image = cv2.imread(str(SCENARIO_DIR / f"{entry['id']}.png"), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Could not decode scenario {entry['id']}")
        result, _ = agent.inspect(f"fixture-{entry['id']}", image, CALIBRATION)
        scenarios.append({
            "id": entry["id"],
            "source": manifest["source"],
            "license": manifest["license"],
            "expected_behavior": entry["expected_behavior"],
            "actual_output": {
                "state": result.state,
                "reading_value": result.reading_value,
                "units": result.units,
                "image_quality_reasons": result.image_quality.get("reasons", []),
                "disagreement_pct_fs": result.normalized_disagreement_pct_fs,
                "tools": [event.tool for event in result.trace],
                "decision_reasons": result.decision_reasons,
            },
        })
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "opencv_version": cv2.__version__,
        "dataset_type": "synthetic_fixture_execution",
        "calibration": CALIBRATION.model_dump(mode="json"),
        "scenarios": scenarios,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "opencv_version": cv2.__version__, "scenarios": [{"id": item["id"], **item["actual_output"]} for item in scenarios]}, indent=2))


if __name__ == "__main__":
    main()
