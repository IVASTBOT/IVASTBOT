# HRI Expression Calibration

This guide describes local Windows calibration for the IVASTBOT HRI expression
pipeline. Calibration data is for manual threshold tuning later; this phase does
not implement automatic tuning.

## Labeled Image Workflow

Use labeled image folders when you want repeatable offline samples:

```text
calibration_images/
  neutral/
  happy/
  surprise/
  confused/
  angry/
  bored/
  unknown/
```

Supported image extensions are `.png`, `.jpg`, and `.jpeg`. Keep the labels
lowercase and use only the folders listed above so mismatches are easy to audit.

Collect around 20-30 samples per label at first. Use varied lighting, head
positions, and expression intensity levels. For bored, collect low-arousal or
repeated neutral-looking samples separately from ordinary neutral samples.

Set the MediaPipe Tasks model path before collecting from images:

```powershell
$env:IVASTBOT_FACE_LANDMARKER_MODEL = "F:\models\face_landmarker.task"
```

Run the image collector from Python so the output path is explicit:

```powershell
python -c "from ivastbot_hri.demos.expression_calibration_collector import collect_from_image_folder, save_calibration_samples, summarize_calibration_samples; samples = collect_from_image_folder('calibration_images'); print(summarize_calibration_samples(samples)); save_calibration_samples(samples, 'calibration_results/expression_samples.json')"
```

The collector does not auto-download model files. If no model path is supplied
and `IVASTBOT_FACE_LANDMARKER_MODEL` is not set, it raises a clear runtime error.

## Webcam Manual Workflow

1. Install optional visual demo dependencies when needed:

   ```powershell
   pip install opencv-python mediapipe
   ```

2. Set the MediaPipe Tasks model path if using MediaPipe 0.10.35 or another
   version without legacy FaceMesh Solutions:

   ```powershell
   $env:IVASTBOT_FACE_LANDMARKER_MODEL = "F:\models\face_landmarker.task"
   ```

3. Run the visual webcam demo:

   ```powershell
   python -m ivastbot_hri.demos.visual_webcam_expression_demo
   ```

4. Exercise each label:

   - neutral
   - happy
   - surprise
   - confused
   - angry
   - bored
   - unknown

5. Record feature scores and labels using
   `ivastbot_hri.demos.expression_calibration_collector`.

Manual webcam samples can use `build_calibration_sample` with `image_path=None`.
This keeps live/debug samples in the same JSON shape as image-folder samples.

## Interpreting Results

Each sample records the expected expression from the label, the predicted
expression from the current recognizer thresholds, and `matched_expected`.
Use mismatches to inspect threshold gaps before changing recognizer constants.
For example, repeated happy-to-neutral mismatches may indicate the smile
threshold is too strict for the current camera and lighting.

## Data Hygiene

Generated calibration JSON files are runtime data. Do not commit them. Do not
commit calibration images. Keep model files such as `face_landmarker.task` out
of git as well.
