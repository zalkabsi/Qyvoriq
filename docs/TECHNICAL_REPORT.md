# Qyvoriq technical report

## Executive summary

Qyvoriq is a calibrated analog-gauge inspection prototype built around OpenCV 5. It pairs a radial Hough-line needle estimate with an annular polar-response estimate and uses image quality, geometry, calibration bounds, and method disagreement to select acceptance, reinspection, or human review. The key result is a traceable abstention workflow, not a novel gauge-reading algorithm.

## Problem and intended users

Maintenance and inspection staff may need to record analog pressure, temperature, or process gauges from photographs. A system that returns an unsupported number can be less useful than one that reports insufficient evidence. Qyvoriq is intended as a demonstration of operator-assistive visual inspection; it is not approved for safety-critical measurement or closed-loop control.

## Prior work and differentiation

Circle/line Hough methods and polar transformations are known image-processing techniques. Prior systems include a CNN mobile gauge transcription system and GAUREAD for circular linear-scale gauges in unstructured scenes. SyncG provides a large synthetic benchmark. Qyvoriq's limited differentiation is a deterministic decision trace in which OpenCV outputs change later actions, with explicit operator reinspection and abstention.

## OpenCV 5 methodology

The pinned Python runtime uses `opencv-python-headless==5.0.0.93`; the tested `cv2.__version__` reports 5.0.0. Pillow is limited to safe format/dimension/EXIF handling before the decoded pixels are passed into OpenCV.

The vision engine performs: grayscale conversion, Laplacian blur, luminance/exposure and contrast measurements, compact saturated-component detection, Canny edges, Hough circles, circular-contour fallback, center-constrained Hough line segments, `warpPolar` annulus response, optional CLAHE refinement, calibrated angle conversion, and OpenCV annotation on a copy.

For a clockwise sweep, Qyvoriq computes `delta = (angle - minimum_angle) mod 360`, `span = (maximum_angle - minimum_angle) mod 360`, and `value = minimum_value + delta/span × full_scale`. Counterclockwise calibration reverses the angular difference. An angle outside the configured sweep remains out of range; it is not silently clamped to the dial maximum.

## Agent policy

`inspect_image` measures quality and localizes the dial. If a quality signal fails its rule, needle estimators are skipped and `request_new_view` returns capture guidance. On a usable image, the geometric and polar methods run. If their numerical disagreement exceeds the validation-derived cap, one CLAHE reinspection runs. Continued disagreement, out-of-range candidates, and exhausted retries request a new user image or escalate to a person. The maximum is two follow-up images. A physical camera is never controlled.

The current cap is stored with provenance in `backend/agents/policy.json`. It was selected from the 95th percentile of disagreements among quality-usable, in-range synthetic validation pairs whose fixed-mean error was no more than 2% full scale. The cutoff is not calibrated on real photos. Quality thresholds remain hand-set heuristics.

## API, frontend, and AWS design

FastAPI exposes image creation, state, result, evidence, and follow-up endpoints. Uploads are limited to 10 MB and 16 MP, then normalized to a 1600-pixel long edge. Source arrays are discarded after analysis. Retained evidence is capped at 100 records and 128 MiB of PNGs, with 30-minute inactivity expiry and a 30-second cleanup sweep. Multipart parsing may use ephemeral OS temporary files; no durable image store is configured. React provides calibration fields, scenario fixtures, image/evidence comparison, trace, and measured evaluations. Calibration is locked during follow-ups; a separate new-inspection action resets the workflow.

The primary AWS judge-demo artifact uses the tested x86 image on ECS Express Mode/Fargate with a managed HTTPS ALB endpoint, private scan-on-push ECR, a Secrets Manager token, and seven-day application logs. A repository-specific GitHub OIDC role enables short-lived deployment credentials. No AWS deployment exists yet; the account owner must apply the access bootstrap first. The account needs a default VPC and public subnets. The older ARM64 template remains a separate advanced design with owner-supplied DNS/ACM. Standard OpenCV wheels are used; COOL has not been executed. There is no durable session store.

## Dataset and experimental design

No external gauge dataset is bundled. The benchmark generator creates synthetic circular dials at known values, with clear, blur, glare, and noise conditions. Deterministic disjoint seed ranges separate validation and test. The validation split fits only the disagreement cap; the test split is evaluated after fitting. The harness compares geometric-only, fixed arithmetic fusion, and the selective agent on identical images.

## Results

See [`docs/EVALUATION.md`](EVALUATION.md) and the structured test result [`benchmarks/results/latest.json`](../benchmarks/results/latest.json). Results are limited to generated synthetic scenes and an x86-64 runtime. They do not establish field accuracy, and no AWS, Graviton, or COOL performance result is claimed.

On the disjoint 120-image synthetic test split, the policy verified 59 images (49.17% coverage), with 0.2793% FS mean absolute error and no accepted error above 5% FS. It requested reinspection for all generated glare and blur samples. The fixed-mean baseline accepted 109 images (90.83%) with 0.2863% FS MAE. The policy accepts fewer images with similar synthetic error; this experiment does not demonstrate improved field reliability or a clear accuracy advantage over fixed fusion.

A separate executed controlled test covers 30 synthetic glare/clear pairs at identical stable dial states. All 30 first images skipped estimators and requested another observation, all 30 clear follow-ups resolved within 2% FS, and all 30 persistent-glare cases reached human escalation at the retry limit. The artifact is `benchmarks/results/reinspection.json`. This measures controlled workflow behavior; it is not a physical camera study.

## Failure analysis

The generated glare and blur conditions are rejected before measurement; the multiple-pointer fixture is outside the supported scope; the digital-meter fixture is not localized as a circular dial. These are software paths, not estimates of how often real scenes will be rejected. Hough localization can choose a wrong circle; correlated estimators can agree on a wrong pointer; glare/exposure heuristics can miss subtle defects.

## Security and responsible use

The app limits untrusted image size/type, avoids persistent image storage, logs trace metadata rather than image data, supports a production bearer token, disables production API docs, and does not control machinery. The one-task AWS design is ephemeral and not hardened as a general production service. Human confirmation remains required.

## References

- [OpenCV 5.0 documentation](https://docs.opencv.org/5.0/).
- [SyncG data descriptor](https://www.nature.com/articles/s41597-026-07308-x).
- [Real-time analogue gauge transcription on mobile phone](https://www.repository.cam.ac.uk/items/6f3bd3df-797b-4ec3-b371-20fd6d756343).
- [GAUREAD](https://doi.org/10.3390/s22176681).
- [OpenCV AI Competition 2026 rules](https://opencv26.devpost.com/rules).
