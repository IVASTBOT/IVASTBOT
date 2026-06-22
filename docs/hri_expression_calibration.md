# HRI Expression Calibration

This guide describes local Windows calibration for the IVASTBOT HRI expression
pipeline. Calibration data is for manual threshold tuning later; this phase does
not implement automatic tuning.

## Manual Workflow

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

## Sample Counts

Collect around 20-30 samples per label at first. Use varied lighting, head
positions, and intensity levels for each expression. For bored, collect
low-arousal or repeated neutral-looking samples separately from ordinary neutral
samples.

## Data Hygiene

Generated calibration JSON files are runtime data. Do not commit them. Keep model
files such as `face_landmarker.task` out of git as well.
