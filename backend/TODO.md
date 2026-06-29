# IVASTBOT IOP TODO

## Members data

- Expand `RAG/database/FRL/members-inf/members.jsonl` from authoritative IOP pages.
- Add stable `member_id` values for every active staff member.
- Fill role dates, unit history, email, profile URL, and aliases.
- Validate records against `members/members.schema.json`.

## Vision

- Collect consent records before setting `consent_for_vision=true`.
- Add real face recognition/image embedding model for `VisionRecognizer._image_embedding()`.
- Store enrollment provenance and image hash.
- Add threshold calibration set with positive and negative examples.
- Document privacy, retention, and consent revocation process before production use.

## Fine-tuning

- No fine-tuning is implemented yet.
- Build an instruction/eval set from approved IOP Q&A after member/RAG data is cleaned.
- Keep RAG as source of truth; fine-tune only behavior/style, not private facts.

## RAG eval expansion

- Add regression questions for each section: introduction, centers, publications, projects, cooperation, seminars.
- Add negative/unknown questions to protect refusal behavior.
- Track source title/section coverage and distance distribution per build.

## Deployment notes

- Pin Python and uv lock once dependency set stabilizes.
- Add documented Ollama model setup for `gemma4:26b` primary and `qwen2.5:3b` fallback.
- Add environment template for paths, thresholds, logging, and model overrides.
