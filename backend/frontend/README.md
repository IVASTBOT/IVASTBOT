# IVASTBOT Frontend

React + Vite + TypeScript MVP for the IVASTBOT local-first AI receptionist.

## Run

Start backend first:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment

Copy `.env.example` to `.env` if you need to override the API URL:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Notes

- Backend is the source of truth for routing.
- Ollama/model warnings are rendered in warning banners.
- Vision is an offline placeholder harness, not production face recognition.

