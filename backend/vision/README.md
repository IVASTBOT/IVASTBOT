# IOP Vision Harness

This is a local-first interface for member recognition. It currently uses a deterministic image fingerprint as a placeholder embedding so the flow can be tested offline. It is not production face recognition.

Rules:
- Only members in `RAG/database/FRL/members-inf/members.jsonl` can be enrolled.
- `consent_for_vision` must be `true`.
- Low-confidence or missing enrollment returns `status: unknown`.
- Replace `VisionRecognizer._image_embedding()` with a real face/image embedding model before production use.
- Do not describe this module as production face recognition until a real model, calibrated thresholds, consent tracking, and privacy review are in place.

CLI:

```bash
python LLM.py enroll-member --member-id <id> --image <path>
python LLM.py vision-query <image_path>
```
