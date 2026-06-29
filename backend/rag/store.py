import os
from typing import Any

from config import COLLECTION, DB_PATH, EMBED_MODEL

_embedder: Any = None
_chroma_client: Any = None
_collection: Any = None
_ollama_client: Any = None


def reset_caches() -> None:
    global _embedder, _chroma_client, _collection, _ollama_client
    _embedder = None
    _chroma_client = None
    _collection = None
    _ollama_client = None


def get_embedder(local_files_only: bool | None = None):
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        if local_files_only is None:
            local_files_only = os.getenv("IVASTBOT_LOCAL_FILES_ONLY", "1") == "1"
        try:
            _embedder = SentenceTransformer(EMBED_MODEL, local_files_only=local_files_only)
        except TypeError:
            _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        import chromadb

        _chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = _chroma_client.get_collection(COLLECTION)
    return _collection


def create_fresh_collection():
    import chromadb

    global _chroma_client, _collection
    _chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
    try:
        _chroma_client.delete_collection(COLLECTION)
    except Exception:
        pass
    _collection = _chroma_client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def get_ollama():
    global _ollama_client
    if _ollama_client is None:
        import ollama

        _ollama_client = ollama
    return _ollama_client
