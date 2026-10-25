# Devpost submission draft

> Draft only. The project owner must verify the live form, final links, team information, and claims before submission. Do not submit the draft until the AWS requirement and video status are accurately represented.

## Project name

Qyvoriq

## Tagline

The vision agent that knows when not to trust its eyes.

## Inspiration

Analog gauges are still used in places where a bad reading matters. A camera-based reader should not always force a number from a blurry, reflective, or ambiguous image. Qyvoriq explores a safer operator workflow: measure the visible evidence, check whether it supports a reading, and ask for another view when it does not.

## What it does

Qyvoriq reads calibrated circular, single-pointer gauges using two OpenCV 5 estimators. It checks image quality, dial geometry, calibration bounds, and estimator disagreement. Depending on those observations, it accepts a reading under an explicit policy, asks the user to submit a new image, or escalates the inspection for human review. Each tool call and decision appears in a trace with an annotated evidence image.

## How it was built

The API is Python 3.12 and FastAPI. OpenCV 5 performs quality assessment, circular localization, center-constrained radial Hough line detection, polar-coordinate needle response, optional CLAHE refinement, and annotation. The web client is React, TypeScript, and Vite. A deterministic orchestration policy makes the next tool call depend on the visual observations. The repository includes a synthetic-only benchmark harness and generated demonstration fixtures.

## Challenges

Two estimates can share the same bad input or wrong dial geometry, so agreement alone is not treated as proof. Calibration must account for image-angle conventions and wraparound. The current controlled synthetic evaluation is useful for software checks but is not a replacement for public benchmark or field images.

## Accomplishments

- A real OpenCV 5 processing path rather than a mocked vision response.
- A traceable decision loop where a glare observation changes the next action.
- Explicit abstention and bounded human follow-up.
- Reproducible code, tests, synthetic results, and deployment artifacts.

## What is incomplete

No AWS endpoint has been deployed in this workspace; no AWS credentials or identity were configured. The application currently uses standard OpenCV 5 wheels and does not claim COOL. No real-gauge benchmark or field test was run. The five-minute video has not been recorded. These requirements must be completed or accurately presented as incomplete before submission.

## Future work

Evaluate on SyncG with its published held-out split, add licensed real captures and a true paired-view evaluation, improve geometry handling for oblique views, test a deployed ARM workload, and only then investigate a reproducible COOL comparison.

## Links to supply

- Public source repository: `https://github.com/zalkabsi/Qyvoriq` (verify the push and public access before submission).
- Working AWS endpoint or arranged live screen-share: **not available yet**.
- Public or unlisted demo video (maximum five minutes): **not recorded yet**.
- Technical report: `docs/TECHNICAL_REPORT.md`.
