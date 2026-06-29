import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "RAG" / "database" / "FRL" / "iop_dataset.json"
MEMBERS_PATH = BASE_DIR / "RAG" / "database" / "FRL" / "members-inf" / "members.jsonl"
MEMBER_IMAGES_DIR = BASE_DIR / "RAG" / "database" / "FRL" / "members-inf" / "images"
VISION_EMBEDDINGS_DIR = BASE_DIR / "RAG" / "database" / "FRL" / "members-inf" / "embeddings"
DB_PATH = BASE_DIR / "iop_chromadb"
COLLECTION = "iop_knowledge"
LOG_PATH = BASE_DIR / "logs" / "brain_requests.jsonl"
RAG_RETRIEVAL_LOG_PATH = BASE_DIR / "logs" / "rag_retrieval.jsonl"

LLM_MODEL_PRIMARY = os.getenv("IVASTBOT_LLM_MODEL", "gemma4:26b")
LLM_MODEL_FALLBACK = os.getenv("IVASTBOT_LLM_FALLBACK", "qwen2.5:3b")
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5
DISTANCE_THRESHOLD = 0.55
MEMBER_NAME_THRESHOLD = 0.82
MEMBER_ROLE_THRESHOLD = 0.72
MEMBER_AMBIGUITY_MARGIN = 0.08
VISION_CONFIDENCE_THRESHOLD = 0.92


def check_ollama_model_available(model_name: str) -> bool:
    try:
        import ollama

        response: Any = ollama.list()
        if isinstance(response, dict):
            models = response.get("models", [])
        else:
            models = getattr(response, "models", response)
        for model in models:
            if isinstance(model, dict):
                name = model.get("name") or model.get("model")
            else:
                name = getattr(model, "model", None) or getattr(model, "name", None)
            if name == model_name:
                return True
        return False
    except Exception:
        return False


def get_model_health() -> dict[str, Any]:
    primary_available = check_ollama_model_available(LLM_MODEL_PRIMARY)
    fallback_available = check_ollama_model_available(LLM_MODEL_FALLBACK)
    warnings: list[str] = []
    active_model = LLM_MODEL_PRIMARY
    if not primary_available:
        warnings.append(f"Primary Ollama model '{LLM_MODEL_PRIMARY}' is not available.")
        if fallback_available:
            active_model = LLM_MODEL_FALLBACK
            warnings.append(f"Using fallback Ollama model '{LLM_MODEL_FALLBACK}'.")
        else:
            warnings.append(f"Fallback Ollama model '{LLM_MODEL_FALLBACK}' is not available.")
    return {
        "model_primary": LLM_MODEL_PRIMARY,
        "model_fallback": LLM_MODEL_FALLBACK,
        "active_model": active_model,
        "primary_available": primary_available,
        "fallback_available": fallback_available,
        "warnings": warnings,
    }
