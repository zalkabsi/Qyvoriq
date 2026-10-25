# Hackathon readiness review

Reviewed on 2026-10-25 against the [official overview](https://opencv26.devpost.com/) and [rules](https://opencv26.devpost.com/rules). This review distinguishes submission completeness from competitive strength. It does not predict a prize or certify absence of all bugs.

## Submission gates

| Gate | Evidence | Current conclusion |
| --- | --- | --- |
| Substantive OpenCV 5 | Actual 5.0.0 runtime; quality, Hough/contour geometry, line/polar estimates, CLAHE and annotation | Implemented and tested locally |
| Visual result changes a later action | Glare skips estimator calls and requests a new observation; disagreement selects refinement; repeated ambiguity escalates | Actual API/browser traces and 30-pair controlled test |
| Meaningful AWS compute | ECS Express Mode template, scoped GitHub OIDC bootstrap, disabled deployment workflow | **Blocked until account owner applies access setup and live processing passes** |
| Endpoint for judges | Local app works; public HTTPS URL is created by the AWS workflow | **No public app URL yet** |
| Video no longer than five minutes | Actual 243.2-second local recording, synthetic English voice, captions, sole-creator credit, seven checked browser submissions | Local preview produced; **final AWS recording and accessible hosting pending** |
| Report, architecture and evaluation | Implemented paths, synthetic data and limitations documented; runtime dependencies locked | Final AWS URL, digest, region, revision and recording evidence must be inserted after execution |
| Repository | Public `zalkabsi/Qyvoriq`; connected integration has push access | Available |
| Submission and eligibility | Owner supplies actual team/eligibility information and submits in Devpost | Owner action |

## Corrections made during this review

- Rejected NaN/infinite and overflowing calibration spans; removed intermediate value rounding that could corrupt agreement when units use very small scale spans.
- Normalized images before expensive vision processing and rejected frames that become too narrow. Bounded complete request bodies before multipart parsing.
- Discarded unused retained source arrays, capped retained evidence at 128 MiB/100 records, and added an expiry sweep.
- Rechecked follow-up eligibility after upload awaits. Added an explicit new-inspection action and locked calibration during continuation.
- Corrected threshold-fitting error normalization for scales other than 0–100.
- Required the saved validation policy at startup; a missing or invalid artifact can no longer silently select a looser threshold.
- Added actual controlled paired-observation success/failure evidence and surfaced it in the Evaluation tab.
- Corrected documentation that had implied uploads never touch temporary disk. Multipart parsing may use short-lived OS files; there is no configured durable image store.
- Added a versioned runtime dependency lock, scoped OIDC access instructions, local/container checks, CloudFormation lint and workflow syntax checks.

## Recorded local checks

- Python suite: **35 passed**, including calibration units/numerical bounds, missing policy rejection, image normalization, memory/expiry limits, token protection, body limits and follow-up behavior. One Starlette `httpx` deprecation warning remains in the test client; it is not a test failure, and the runtime version is locked.
- TypeScript/Vite production build, Ruff, all CloudFormation templates and workflow syntax checks passed. The complete Python demo/development dependency audit and the full Node audit reported no known vulnerabilities at review time.
- The rebuilt production container ran as UID 10001 and passed actual HTTP health/auth/clear/glare/follow-up/ambiguous/unsupported/evidence checks. Browser checks verified locked continuation calibration, a clean new-inspection reset, and a small-unit reading without rounding it to zero. See [local production evidence](evidence/local-production.json).
- The actual 243.2-second preview has H.264 video, stereo AAC narration, captions and seven checked browser submissions. Audio was present without clipping, and title/evaluation frames were visually inspected. See [recording evidence](evidence/local-preview.json).
- The [GitHub identity check](https://github.com/zalkabsi/Qyvoriq/actions/runs/40202662188) passed and established the exact OIDC subject. This does not establish AWS authorization until the account owner creates the role.

## Competitive assessment

The following ranges are reviewer judgment about the present evidence, not measurements or expected judge scores.

| Rubric | Weight | Current estimated range | Evidence and main gap |
| --- | ---: | ---: | --- |
| Technical execution | 30 | 18–23 | Real two-method OpenCV implementation and bounded agent loop; geometry remains narrow and heuristic |
| Innovation | 20 | 7–11 | Useful observable abstention workflow; gauge reading and the estimator methods are established techniques |
| Real-world impact | 20 | 4–8 | Plausible inspection problem; no licensed real-photo evaluation, field study, or operator benefit measured |
| User experience | 10 | 7–9 | Calibration, evidence, trace, clear reset/follow-up behavior and responsive interface |
| Documentation/presentation | 10 | 7–9 | Reproducible outputs and candid limitations; final AWS evidence/video link still missing |
| Cloud/reproducibility/responsible operation | 10 | 1–3 | Locally checked artifacts, dependency lock and access plan; no executed AWS workload yet |

The selective agent has similar synthetic error to fixed fusion while accepting roughly half as many images. The existing test set contains no accepted error above 5% FS for either method, so it does not show that abstention prevented a dangerous reading. The 30 paired cases demonstrate controlled recovery and retry handling, not field effectiveness. These are material limitations for the impact and innovation scores. A grand-prize claim is not supported by current evidence.

## Next acceptance check

After AWS access is configured: inspect the running task and network settings, exercise the deployed API and browser flow, save the actual URL/image digest/OpenCV version/architecture/revision, record the deployed workflow with narration, verify the exported duration/audio/captions, and update all report statuses. Only then review the public video link and Devpost form with the owner. COOL is optional and is not claimed.
