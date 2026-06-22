# HRI Expression Classifier

Phase 16 adds a small trainable expression classifier for IVASTBOT HRI. The
classifier trains on extracted feature-score dictionaries from calibration JSON,
not raw images.

## Why This Classifier Is Lightweight

The first trainable model is a pure-Python nearest-centroid classifier. It does
not require sklearn. It also avoids torch, tensorflow, OpenCV, MediaPipe, ROS 2,
webcam access, and robot hardware. It averages feature vectors per expression
label and predicts the nearest expression centroid.

Supported labels are:

- neutral
- happy
- surprise
- confused
- angry
- bored
- unknown

Predictions use internal expression keys such as `EXPR_HAPPY` and
`EXPR_ANGRY`.

## Collect Samples First

Use the Phase 14 calibration collector to build a JSON file of labeled feature
samples. The classifier expects sample objects with at least:

```json
{
  "label": "happy",
  "features": {
    "smile_score": 0.9,
    "face_confidence": 0.95
  }
}
```

## Train A Classifier JSON

Run the local training helper with explicit input and output paths:

```powershell
python -m ivastbot_hri.demos.train_expression_classifier --input F:\IVASTBOT_WORK\calibration\expression_samples.json --output F:\IVASTBOT_WORK\models\expression_classifier.json
```

The command prints an evaluation summary and writes classifier JSON only to the
provided output path. Do not commit generated classifier JSON, calibration data,
model weights, or raw image datasets.

## Evaluate Accuracy And Confusion

Training uses deterministic splitting. Evaluation reports:

- total samples
- correct predictions
- accuracy
- per-label accuracy
- confusion summary

Review confusion before integrating the classifier into a demo. If happy samples
are confused with neutral, collect more happy and neutral examples before
changing the model boundary. If angry and confused overlap, inspect brow and
eye-squint features.

## Future Integration

This phase does not replace the rule-based `ExpressionRecognizer`.
It also does not change the visual webcam demo by default. A later phase can
optionally load a classifier JSON from an environment variable and compare
classifier predictions against the existing rule-based recognizer.

## Optional Visual Demo Integration

Phase 17 lets the visual webcam demo use a trained classifier JSON only when
`IVASTBOT_EXPRESSION_CLASSIFIER_MODEL` is set:

```powershell
$env:IVASTBOT_EXPRESSION_CLASSIFIER_MODEL = "F:\IVASTBOT_WORK\models\expression_classifier.json"
python -m ivastbot_hri.demos.visual_webcam_expression_demo
```

If the environment variable is missing or empty, the demo keeps using the
rule-based `ExpressionRecognizer`. The overlay shows `recognizer_mode: rule` or
`recognizer_mode: classifier` so manual testing can confirm which path is active.

For side-by-side debugging, enable comparison mode:

```powershell
$env:IVASTBOT_COMPARE_RECOGNIZERS = "1"
$env:IVASTBOT_EXPRESSION_CLASSIFIER_MODEL = "F:\IVASTBOT_WORK\models\expression_classifier.json"
python -m ivastbot_hri.demos.visual_webcam_expression_demo
```

Comparison mode overlays the rule expression, classifier expression, final
selected expression, smoothed expression, and whether the recognizers disagree.
Set `IVASTBOT_PREFER_CLASSIFIER=1` to prefer classifier output when it is
available and not `EXPR_UNKNOWN`.
