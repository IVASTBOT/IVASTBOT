"""
IOP RAG Pipeline — Local Chatbot cho Viện Vật lý
================================================
Cài đặt:
    pip install chromadb sentence-transformers ollama

Cần có Ollama chạy local:
    ollama pull qwen2.5:7b          # hoặc llama3.2:3b nếu RAM ít
    ollama serve                    # khởi động server (thường tự động)

Chạy:
    python rag_pipeline.py build    # lần đầu: build vector DB
    python rag_pipeline.py chat     # chat với chatbot
    python rag_pipeline.py query "Viện Vật lý có bao nhiêu trung tâm?"
"""

import sys
import json
from pathlib import Path

# ─────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────

DATASET_PATH = "iop_dataset.json"   # file JSON đã cào
DB_PATH      = "./iop_chromadb"     # thư mục lưu vector DB
COLLECTION   = "iop_knowledge"

# Model embedding — chạy local, không cần internet sau lần đầu download
EMBED_MODEL  = "paraphrase-multilingual-MiniLM-L12-v2"  # hỗ trợ tiếng Việt

# LLM local qua Ollama — đổi thành llama3.2:3b nếu RAM < 8GB
LLM_MODEL    = "qwen2.5:7b"

CHUNK_SIZE   = 500   # số ký tự mỗi chunk
CHUNK_OVERLAP = 100  # overlap giữa các chunk
TOP_K        = 4     # số chunk lấy ra để trả lời

# ─────────────────────────────────────────
# CHUNK TEXT
# ─────────────────────────────────────────

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list[str]:
    """Chia text thành các đoạn nhỏ có overlap."""
    chunks = []
    start  = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if len(c) > 50]

# ─────────────────────────────────────────
# BUILD VECTOR DB
# ─────────────────────────────────────────

def build_db():
    import chromadb
    from sentence_transformers import SentenceTransformer

    print("📦 Đang load dataset...")
    with open(DATASET_PATH, encoding="utf-8") as f:
        records = json.load(f)
    print(f"   {len(records)} records")

    print(f"\n🔠 Đang load embedding model: {EMBED_MODEL}")
    embedder = SentenceTransformer(EMBED_MODEL)

    print(f"\n🗄  Khởi tạo ChromaDB tại: {DB_PATH}")
    client     = chromadb.PersistentClient(path=DB_PATH)
    # Xoá collection cũ nếu rebuild
    try:
        client.delete_collection(COLLECTION)
    except:
        pass
    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    print("\n✂  Đang chunk và embed...")
    all_chunks = []
    all_ids    = []
    all_metas  = []

    for rec in records:
        chunks = chunk_text(rec["content"])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{rec['section']}_{hash(rec['url'])}_{i}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metas.append({
                "section": rec["section"],
                "title":   rec["title"],
                "url":     rec["url"],
            })

    print(f"   Tổng chunks: {len(all_chunks)}")

    # Embed và insert theo batch
    BATCH = 64
    for i in range(0, len(all_chunks), BATCH):
        batch_texts = all_chunks[i:i+BATCH]
        batch_ids   = all_ids[i:i+BATCH]
        batch_metas = all_metas[i:i+BATCH]
        embeddings  = embedder.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            documents=embeddings,
            ids=batch_ids,
            metadatas=batch_metas,
        )
        # Lưu text riêng vì ChromaDB free tier không search by text với custom embed
        # → lưu lại map chunk_id -> text
    
    # Lưu chunk texts ra file để retrieve sau
    chunks_map = {cid: txt for cid, txt in zip(all_ids, all_chunks)}
    with open(f"{DB_PATH}/chunks_map.json", "w", encoding="utf-8") as f:
        json.dump(chunks_map, f, ensure_ascii=False)

    print(f"\n✅ Build xong! {len(all_chunks)} chunks đã được index vào ChromaDB")
    print(f"   Thư mục DB: {DB_PATH}")

# ─────────────────────────────────────────
# RETRIEVE
# ─────────────────────────────────────────

def retrieve(query: str, top_k=TOP_K):
    import chromadb
    from sentence_transformers import SentenceTransformer

    embedder   = SentenceTransformer(EMBED_MODEL)
    client     = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(COLLECTION)

    # Load chunk texts
    with open(f"{DB_PATH}/chunks_map.json", encoding="utf-8") as f:
        chunks_map = json.load(f)

    query_vec = embedder.encode([query])[0].tolist()
    results   = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
    )

    chunks = []
    for i, cid in enumerate(results["ids"][0]):
        text  = chunks_map.get(cid, "")
        meta  = results["metadatas"][0][i]
        chunks.append({"text": text, "meta": meta})
    return chunks

# ─────────────────────────────────────────
# GENERATE (Ollama)
# ─────────────────────────────────────────

def generate(query: str, context_chunks: list) -> str:
    import ollama

    # Ghép context
    context = "\n\n---\n\n".join(
        f"[{c['meta']['title']}]\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""Bạn là trợ lý thông minh của Viện Vật lý (IOP), thuộc Viện Hàn lâm Khoa học và Công nghệ Việt Nam.
Hãy trả lời câu hỏi dựa trên thông tin được cung cấp bên dưới.
Nếu thông tin không đủ để trả lời, hãy nói rõ điều đó.
Trả lời bằng tiếng Việt, ngắn gọn và chính xác.

=== THÔNG TIN THAM KHẢO ===
{context}

=== CÂU HỎI ===
{query}

=== TRẢ LỜI ==="""

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
    )
    return response["message"]["content"]

# ─────────────────────────────────────────
# QUERY (1 câu hỏi)
# ─────────────────────────────────────────

def ask(query: str, verbose=False):
    print(f"\n🔍 Câu hỏi: {query}")
    chunks = retrieve(query)

    if verbose:
        print(f"\n📎 Context tìm được ({len(chunks)} chunks):")
        for c in chunks:
            print(f"  [{c['meta']['title']}] {c['text'][:100]}...")

    print("\n⏳ Đang sinh câu trả lời...")
    answer = generate(query, chunks)
    print(f"\n💬 Trả lời:\n{answer}")

    # In nguồn
    sources = list({c["meta"]["url"] for c in chunks})
    print(f"\n📚 Nguồn:")
    for s in sources:
        print(f"  {s}")
    return answer

# ─────────────────────────────────────────
# CHAT LOOP
# ─────────────────────────────────────────

def chat():
    print("=" * 55)
    print("  IOP CHATBOT — Viện Vật lý")
    print("  Gõ 'exit' để thoát")
    print("=" * 55)
    while True:
        try:
            q = input("\n❓ Bạn hỏi: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt!")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "thoat"):
            print("Tạm biệt!")
            break
        ask(q)

# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"

    if cmd == "build":
        build_db()
    elif cmd == "chat":
        chat()
    elif cmd == "query":
        q = " ".join(sys.argv[2:])
        if not q:
            print("Usage: python rag_pipeline.py query <câu hỏi>")
        else:
            ask(q, verbose=True)
    else:
        print("Usage:")
        print("  python rag_pipeline.py build")
        print("  python rag_pipeline.py chat")
        print('  python rag_pipeline.py query "câu hỏi"')