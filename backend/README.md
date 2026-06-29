# IVASTBOT IOP Local RAG Backend

Local-first chatbot backend for IOP-VAST using Ollama, ChromaDB, and SentenceTransformer.

## Setup

```bash
uv sync
ollama serve
ollama pull gemma4:26b
ollama pull qwen2.5:3b
IVASTBOT_ALLOW_DOWNLOAD=1 python LLM.py build
```

`gemma4:26b` is the primary Ollama model. `qwen2.5:3b` is fallback/debug only. Override with `IVASTBOT_LLM_MODEL` and `IVASTBOT_LLM_FALLBACK`.

```bash
export IVASTBOT_LLM_MODEL=gemma4:26b
export IVASTBOT_LLM_FALLBACK=qwen2.5:3b
```

After the embedding model is cached, normal build/query mode defaults to local files only via `IVASTBOT_LOCAL_FILES_ONLY=1`. Use `IVASTBOT_ALLOW_DOWNLOAD=1` only for first-time setup or model refresh.

## CLI

```bash
python LLM.py build
python LLM.py test-time
python LLM.py query "hello"
python LLM.py query "giám đốc trung tâm vật lý lý thuyết là ai"
python LLM.py chat
python LLM.py enroll-member --member-id <id> --image <path>
python LLM.py vision-query <image_path>
```

## API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# or
scripts/run_backend.sh
```

Endpoints:

- `GET /health`
- `POST /chat`
- `POST /rag/query`
- `POST /members/lookup`
- `POST /vision/recognize`
- `POST /vision/enroll`

`/vision/recognize` and `/vision/enroll` use explicit JSON `image_path` fields. The current vision module is a local placeholder harness, not production face recognition.

## Frontend

Run the backend first:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then run the React/Vite MVP:

```bash
cd frontend
npm install
npm run dev
# or from backend root
scripts/run_frontend.sh
```

The frontend uses `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.

Open `http://localhost:5173`.

## End-to-End Smoke Test

Start the backend first:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then run:

```bash
python scripts/e2e_smoke.py
# or
scripts/run_e2e.sh
```

The smoke test checks `/health`, `/chat`, `/members/lookup`, and `/vision/recognize`.

## Local-first Notes

- If Ollama is not running or `gemma4:26b`/`qwen2.5:3b` are unavailable, RAG returns warnings and the backend/UI should not crash.
- Vision is currently an offline placeholder/fingerprint harness, not production face recognition.
- Fine-tuning is not part of this phase.

## Tests

```bash
python LLM.py build
python LLM.py test-time
pytest -q
```
