# HRI Threshold Tuning

This guide explains how to analyze expression calibration samples and tune the
rule-based `ExpressionRecognizer` thresholds. This phase is threshold tuning,
not classifier training.

## Collect Samples

Use the Phase 14 collector to create calibration samples from labeled image
folders or manual webcam/debug observations:

```powershell
python -c "from ivastbot_hri.demos.expression_calibration_collector import collect_from_image_folder, save_calibration_samples; samples = collect_from_image_folder('calibration_images'); save_calibration_samples(samples, 'calibration_results/expression_samples.json')"
```

Do not commit calibration images, model files, or generated calibration result
JSON files.

## Run The Analyzer

Analyze a saved sample file:

```powershell
python -m ivastbot_hri.demos.calibration_analyzer calibration_results/expression_samples.json --output calibration_results/threshold_recommendations.json
```

The analyzer is local and dependency-free at import time. It does not open a
webcam, load OpenCV, load MediaPipe, require ROS 2, or train a model.

## Interpret Accuracy

The analyzer reports per-label counts, matched predictions, mismatched
predictions, and accuracy. Low per-label accuracy usually means the current
thresholds are too strict, too loose, or the collected sample set is not balanced
enough for that expression.

Review the confusion summary before changing thresholds. For example, if many
happy samples are predicted as neutral, inspect `happy_smile_threshold`. If angry
samples are predicted as neutral, inspect `angry_brow_down_threshold` and
`angry_eye_squint_threshold`.

## Use Recommended Thresholds

Recommended thresholds are conservative statistics from the collected feature
distributions. They can be loaded into a recognizer with
`build_expression_recognizer_from_thresholds`:

```python
from ivastbot_hri.demos.calibration_analyzer import (
    build_expression_recognizer_from_thresholds,
    load_calibration_samples,
    recommend_thresholds,
)

samples = load_calibration_samples("calibration_results/expression_samples.json")
recommendations = recommend_thresholds(samples)
recognizer = build_expression_recognizer_from_thresholds(recommendations)
```

Keep the existing defaults until a label has enough varied samples. When the
rule-based thresholds cannot separate labels reliably, that is the point to
consider a later classifier-training phase.
