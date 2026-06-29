from typing import Any

from fastapi import FastAPI
try:
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:
    CORSMiddleware = None
from pydantic import BaseModel, Field

from brain.harness import BrainHarness
from brain.response import BrainRequest
from config import COLLECTION, DB_PATH, EMBED_MODEL, get_model_health
from members.resolver import lookup_member
from rag.generator import generate
from rag.retriever import retrieve
from vision.enrollment import enroll_member
from vision.cv_service import recognize_image

app = FastAPI(title="IVASTBOT IOP RAG API", version="0.1.0")
if CORSMiddleware is not None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
brain = BrainHarness()


class ChatPayload(BaseModel):
    query: str
    mode: str = "auto"
    image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryPayload(BaseModel):
    query: str
    top_k: int = 5


class MemberPayload(BaseModel):
    query: str


class VisionPayload(BaseModel):
    image_path: str


class EnrollPayload(BaseModel):
    member_id: str
    image_path: str


@app.get("/health")
def health() -> dict[str, Any]:
    model = get_model_health()
    return {
        "status": "ok",
        "embedding_model": EMBED_MODEL,
        "vector_db": {
            "path": str(DB_PATH),
            "exists": DB_PATH.exists(),
            "collection": COLLECTION,
            "sqlite_exists": (DB_PATH / "chroma.sqlite3").exists(),
        },
        **model,
    }


@app.post("/chat")
def chat(payload: ChatPayload) -> dict[str, Any]:
    req = BrainRequest(query=payload.query, mode=payload.mode, image_path=payload.image_path, metadata=payload.metadata)
    return brain.handle(req).to_dict()


@app.post("/rag/query")
def rag_query(payload: QueryPayload) -> dict[str, Any]:
    chunks = retrieve(payload.query, top_k=payload.top_k)
    answer = generate(payload.query, chunks)
    return {"answer": answer, "chunks": chunks}


@app.post("/members/lookup")
def members_lookup(payload: MemberPayload) -> dict[str, Any]:
    return lookup_member(payload.query)


@app.post("/vision/recognize")
def vision_recognize(payload: VisionPayload) -> dict[str, Any]:
    return recognize_image(payload.image_path)


@app.post("/vision/enroll")
def vision_enroll(payload: EnrollPayload) -> dict[str, Any]:
    return enroll_member(payload.member_id, payload.image_path)
