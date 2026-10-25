# Research and method selection

## Existing gauge-reading approaches

Analog-gauge readers commonly separate the problem into dial localization, pointer/scale geometry, and calibration. Classical implementations use circle or contour evidence for the dial and line evidence for the pointer. OpenCV documents the Hough line transform and gradient-based Hough circle transform as general primitives; they do not solve gauge interpretation by themselves. Radial ticks, strong rim edges, reflections, oblique views, and low contrast can create competing evidence.

Learning-based systems can estimate keypoints, segment the pointer, or map an image to a reading. Howells et al. describe a CNN-based mobile gauge reader and release both synthetic and real gauge datasets. GAUREAD targets circular linear-scale gauges in less structured environments. These systems demonstrate that calibrated geometric processing is not new, and that real-photo variation matters. Qyvoriq does not claim to outperform them.

OpenCV's `warpPolar` makes angular structure explicit. A radial pointer becomes a localized angular response in a polar image. Qyvoriq uses that representation as a second estimator alongside radial Hough line candidates. Both estimators share the same input image and localized circle geometry; they are partially independent in their final evidence extraction, not statistically independent sensors.

## SyncG

The peer-reviewed [SyncG data descriptor](https://www.nature.com/articles/s41597-026-07308-x) reports 20,000 photorealistic synthetic gauge images across 145 environmental settings and annotations for object detection, keypoint localization, segmentation, and OCR. The article describes a CC BY 4.0 release. The [Hugging Face dataset page](https://huggingface.co/datasets/YihengDeng/syncG) lists the dataset and train/test splits.

The dataset files and card schema could not be inspected from this executor, and the dataset is not bundled, downloaded, or evaluated in this project. Therefore Qyvoriq makes no claim about results on SyncG and does not use its labels. Before future integration, inspect the current dataset card, verify the exact schema and licensing, record the published split manifest, and evaluate only on its held-out split.

## Selected implementation

1. Validate JPEG/PNG/WebP decoding, image bounds, and EXIF orientation.
2. Measure blur, exposure, contrast, and compact saturated glare regions with OpenCV.
3. Localize one circular dial using Hough circles and circular-contour validation.
4. Estimate a radial needle candidate with `HoughLinesP`, requiring a line close to the dial center and long enough to be pointer evidence.
5. Apply `warpPolar` to the grayscale observation and search an annulus for a localized dark response by angle.
6. Convert both angles through the user-provided endpoints and sweep direction. Values outside the calibrated sweep are not silently clamped.
7. Compare the two estimates using full-scale span. If they disagree, apply one CLAHE pass and recompute; unresolved evidence triggers an operator-requested new image or human review.
8. Draw an evidence overlay on a copy of the original.

The current quality cutoffs are explicit engineering heuristics. They are not probabilities and are not calibrated on field photographs. The method records metrics and flags, not an arbitrary confidence percentage.

## What is and is not novel

Hough-based localization, geometric needle angles, polar representations, calibration, and image-quality checks are established techniques. Qyvoriq's contribution is a small, inspectable decision loop around these operations: visual quality can prevent the estimators from running, disagreement can select a refinement pass, and unresolved evidence can request another observation or human review. Each action appears in a trace and has a test fixture.

This is an engineering integration and product claim, not a new vision algorithm or a validated reliability guarantee. The active-view scenario is controlled synthetic input; it does not show a physical camera being moved.

## Sources

- Deng et al., [A Large-Scale Synthetic Benchmark for Robust Analog Gauge Reading](https://www.nature.com/articles/s41597-026-07308-x), *Scientific Data*, 2026.
- [SyncG dataset page](https://huggingface.co/datasets/YihengDeng/syncG).
- Howells et al., [Real-time analogue gauge transcription on mobile phone](https://www.repository.cam.ac.uk/items/6f3bd3df-797b-4ec3-b371-20fd6d756343), CVPR Workshops, 2021.
- [GAUREAD: Autonomous Reading of Gauges in Unstructured Environments](https://doi.org/10.3390/s22176681), *Sensors*, 2022.
- [OpenCV 5 Hough Line Transform](https://docs.opencv.org/5.0/tutorials/imgproc/imgtrans/hough_lines/hough_lines.html).
- [OpenCV 5 Hough Circle Transform](https://docs.opencv.org/5.0/tutorials/imgproc/imgtrans/hough_circle/hough_circle.html).
- [OpenCV 5 geometric transforms](https://docs.opencv.org/5.0/main_modules/imgproc_transform.html), including polar mappings.
