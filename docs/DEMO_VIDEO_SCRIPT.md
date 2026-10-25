# Five-minute demo video script

**Status:** final AWS recording and public/unlisted hosting pending. `scripts/record_demo.py` produces an actual narrated screen recording with captions. Local runs are marked `LOCAL PREVIEW · AWS DEPLOYMENT PENDING`; final mode requires a passing deployment-evidence file. The confirmed team is sole creator **Zein Alkabsi**, using the connected GitHub display name. No human footage is fabricated. Narration uses the stock `en-US-EmmaMultilingualNeural` voice through the user-authorized `speech.platform.bing.com` endpoint.

The generated narration uses the actual benchmark API values. A local preview is an editing and workflow artifact; it is not AWS proof or the final submitted video.

The first actual narrated local export was **243.2 seconds (4:03.2)** at 1600×1000, H.264/AAC, with seven checked browser submissions and burned-in captions. Its scope and executed states are recorded in `docs/evidence/local-preview.json`. The public/unlisted final AWS video has not been produced or hosted yet.

| Time | Shot / on-screen text | Voiceover and action |
| --- | --- | --- |
| 0:00–0:25 | Team introduction, title “Qyvoriq” | Identify the project and real-world problem: a reader should abstain when the photo does not support a trustworthy value. Do not invent team size or experience. |
| 0:25–1:05 | Inspection workspace, calibration fields | Show a generated clear gauge, explain min/max, units, image angle convention, and that calibration is user-supplied. Run the inspection and show the returned value and overlay. Caption: “Synthetic fixture; not field validation.” |
| 1:05–2:05 | Load “Glass reflection” | Show quality metrics, `request_new_view`, and the trace. Point out that estimator tools were skipped. Submit the paired clear control image with the same generated dial state. Label it “controlled synthetic follow-up, not a camera capture.” |
| 2:05–2:45 | Show unsupported/ambiguous cases | Load the two-pointer and digital-meter fixtures. Explain the supported scope and show abstention or escalation. Do not describe generated data as real. |
| 2:45–3:30 | Architecture diagram | Walk through React, FastAPI, OpenCV 5 quality/localization, two estimators, deterministic policy, and the user follow-up loop. State that estimator errors can be correlated. |
| 3:30–4:15 | Evaluation tab and JSON result | Show actual latest test counts, metrics, split/seed, and synthetic-only label. Include one failure example. Explain full-scale normalized error and the 5% FS false-accept definition. |
| 4:15–4:45 | AWS status and repo | If deployed by the owner, show the live HTTPS endpoint, region, ARM architecture, and logs. Otherwise say AWS deployment is incomplete; do not present the template as a live service. Show repository and setup command. |
| 4:45–4:58 | Closing card | State what is measured, what remains unvalidated, and the human role. Keep total at or below 4:58. |

## Recording checklist

- Record actual team members and only the roles they approve. Do not imply the agent authored work manually or present generated scenes as photographs.
- Capture the screen at readable scale; include captions for tool decisions and data source.
- Show the AWS endpoint only if it has been deployed and independently checked. A local app is not AWS proof.
- Show the generated benchmark JSON and repository commit used in the recording.
- Keep the final video below five minutes and publish it public/unlisted with access enabled for judges.

## Generate a recording

Install `requirements-demo.txt` and system Chromium/FFmpeg. Start a built app locally, then run:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.record_demo \
  --url http://127.0.0.1:8000 --output demo-output/local \
  --team 'Zein Alkabsi' --preview
```

For the final recording, use the actual HTTPS AWS URL, set `QYVORIQ_API_TOKEN` through the environment, omit `--preview`, and supply `--deployment-evidence` from the passing HTTP smoke check. The script records real browser requests and asserts clear, glare, follow-up, bounded human escalation and unsupported states. It exports a captioned MP4, narration audio, SRT captions, screenshots and a timing/check manifest, and rejects an export over five minutes. Never publish the token value or source credential files.
