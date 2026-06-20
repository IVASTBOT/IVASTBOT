"""
IOP RAG Pipeline — Local Chatbot cho Viện Vật lý
================================================
Cài đặt:
    pip install chromadb sentence-transformers ollama mcp

Cần có Ollama chạy local:
    ollama pull qwen2.5:7b          # hoặc llama3.2:3b nếu RAM ít
    ollama serve                    # khởi động server (thường tự động)

Chạy:
    python LLM.py build             # lần đầu: build vector DB
    python LLM.py chat              # chat với chatbot
    python LLM.py query "Viện Vật lý có bao nhiêu trung tâm?"
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# ─────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────

BASE_DIR      = Path(__file__).parent
DATASET_PATH  = BASE_DIR / "RAG" / "database" / "FRL" / "iop_dataset.json"
DB_PATH       = BASE_DIR / "iop_chromadb"
COLLECTION    = "iop_knowledge"

# Model embedding — chạy local, không cần internet sau lần đầu download
EMBED_MODEL   = "paraphrase-multilingual-MiniLM-L12-v2"  # hỗ trợ tiếng Việt

# LLM local qua Ollama
LLM_MODEL     = "qwen3.5:latest"

TOP_K         = 5      # số chunk lấy ra để trả lời

# Cosine distance threshold — nếu chunk gần nhất > threshold này, bỏ qua
DISTANCE_THRESHOLD = 0.55

# ─────────────────────────────────────────
# SMART CHUNKING — chia theo loại record
# ─────────────────────────────────────────

def _detect_record_type(content: str) -> str:
    """Phát hiện loại record để chọn chiến lược chunk phù hợp."""
    # Bảng nhân sự: có pattern "số thứ tự + tên + học vị + chức danh"
    if re.search(r'(\n|^)\d+\s+\S+.*(?:PGS|TS|ThS|GS|KS|Kỹ sư|Thạc sĩ)', content):
        return "nhan_su"
    # Danh sách công bố: có DOI, arXiv, tạp chí
    if re.search(r'(?:doi|arXiv|tạp chí|Tạp chí|kỷ yếu|proceedings)', content, re.I):
        return "cong_bo"
    # Văn bản ngắn
    if len(content) < 800:
        return "ngan"
    # Văn bản dài mặc định
    return "van_ban"


def _chunk_nhan_su(content: str, title: str) -> List[str]:
    """
    Chia bảng nhân sự theo người.
    Mỗi dòng trong bảng = 1 chunk, prepend title để giữ context.
    Giữ lại phần header (giám đốc, phó giám đốc) riêng.
    """
    chunks = []
    lines = content.strip().split('\n')
    header_lines = []
    person_lines = []

    in_table = False
    for line in lines:
        # Phát hiện dòng bắt đầu bảng (có STT ở đầu)
        if re.match(r'^\s*\d+\s+', line.strip()):
            in_table = True
            person_lines.append(line.strip())
        elif in_table:
            person_lines.append(line.strip())
        else:
            header_lines.append(line.strip())

    # Header chunk: giám đốc, phó giám đốc, mô tả trung tâm
    header_text = '\n'.join(l for l in header_lines if l)
    if header_text:
        chunks.append(f"[{title}]\n{header_text}")

    # Mỗi người = 1 chunk, prepend tên trung tâm từ title
    center_name = title.replace(" - Nhân lực", "").replace(" - Nhân sự", "")
    for line in person_lines:
        if line.strip():
            chunks.append(f"[{title}] {center_name} | {line.strip()}")

    return chunks if chunks else [f"[{title}]\n{content.strip()}"]


def _chunk_cong_bo(content: str, title: str) -> List[str]:
    """
    Chia danh sách công bố theo từng mục.
    Thường mỗi công bố nằm trên 1-2 dòng.
    """
    chunks = []
    lines = content.strip().split('\n')
    current_item = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_item:
                text = '\n'.join(current_item)
                if len(text) > 30:
                    chunks.append(f"[{title}]\n{text}")
                current_item = []
            continue
        # Dòng mới bắt đầu bằng số hoặc bullet
        if re.match(r'^[\d\-\•\▪▸●○◉]', stripped) or re.match(r'^\[\d{4}\]', stripped):
            if current_item:
                text = '\n'.join(current_item)
                if len(text) > 30:
                    chunks.append(f"[{title}]\n{text}")
            current_item = [stripped]
        else:
            current_item.append(stripped)

    if current_item:
        text = '\n'.join(current_item)
        if len(text) > 30:
            chunks.append(f"[{title}]\n{text}")

    return chunks if chunks else [f"[{title}]\n{content.strip()}"]


def _chunk_van_ban(content: str, title: str, max_size=800, overlap=150) -> List[str]:
    """
    Chia văn bản dài theo đoạn (paragraph), không cắt ngang câu.
    Prepend title vào mỗi chunk.
    """
    paragraphs = re.split(r'\n\s*\n', content.strip())
    chunks = []
    current = f"[{title}]\n"

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Nếu thêm đoạn này vẫn < max_size → gộp
        if len(current) + len(para) + 2 <= max_size:
            current += para + "\n\n"
        else:
            # Lưu chunk hiện tại
            if len(current.strip()) > 50:
                chunks.append(current.strip())
            current = f"[{title}]\n{para}\n\n"

    # Chunk cuối
    if len(current.strip()) > 50:
        chunks.append(current.strip())

    return chunks if chunks else [f"[{title}]\n{content.strip()}"]


def smart_chunk(record: dict) -> List[str]:
    """
    Chia 1 record thành chunks thông minh dựa trên loại nội dung.
    Mọi chunk đều prepend [title] để embedding giữ context.
    """
    content = record["content"]
    title   = record["title"]
    rtype   = _detect_record_type(content)

    if rtype == "nhan_su":
        return _chunk_nhan_su(content, title)
    elif rtype == "cong_bo":
        return _chunk_cong_bo(content, title)
    elif rtype == "ngan":
        return [f"[{title}]\n{content.strip()}"]
    else:
        return _chunk_van_ban(content, title)


# ─────────────────────────────────────────
# BUILD VECTOR DB
# ─────────────────────────────────────────

def build_db():
    import chromadb
    from sentence_transformers import SentenceTransformer

    print("=" * 55)
    print("  BUILD IOP VECTOR DATABASE")
    print("=" * 55)

    print("\n📦 Đang load dataset...")
    with open(DATASET_PATH, encoding="utf-8") as f:
        records = json.load(f)
    print(f"   {len(records)} records")

    print(f"\n🔠 Đang load embedding model: {EMBED_MODEL}")
    embedder = SentenceTransformer(EMBED_MODEL)

    print(f"\n🗄  Khởi tạo ChromaDB tại: {DB_PATH}")
    client = chromadb.PersistentClient(path=str(DB_PATH))
    # Xoá collection cũ nếu rebuild
    try:
        client.delete_collection(COLLECTION)
    except:
        pass
    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    print("\n✂  Đang smart-chunk và embed...")
    all_chunks = []
    all_ids    = []
    all_metas  = []

    for rec in records:
        chunks = smart_chunk(rec)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{rec['section']}_{i}_{abs(hash(rec['url'])) % 10000}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metas.append({
                "section": rec["section"],
                "title":   rec["title"],
                "url":     rec["url"],
            })

    print(f"   Tổng chunks: {len(all_chunks)} (trước: ~{len(records) * 3} với chunk cứng 500 ký tự)")

    # Embed và insert theo batch
    BATCH = 64
    for i in range(0, len(all_chunks), BATCH):
        batch_texts = all_chunks[i:i+BATCH]
        batch_ids   = all_ids[i:i+BATCH]
        batch_metas = all_metas[i:i+BATCH]
        embeddings  = embedder.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            documents=batch_texts,   # Lưu luôn text vào ChromaDB
            embeddings=embeddings,
            ids=batch_ids,
            metadatas=batch_metas,
        )
        if (i // BATCH + 1) % 5 == 0 or i + BATCH >= len(all_chunks):
            print(f"   Đã xử lý {min(i+BATCH, len(all_chunks))}/{len(all_chunks)} chunks")

    # Lưu chunk texts ra file backup
    chunks_map = {cid: txt for cid, txt in zip(all_ids, all_chunks)}
    with open(f"{DB_PATH}/chunks_map.json", "w", encoding="utf-8") as f:
        json.dump(chunks_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Build xong! {len(all_chunks)} chunks đã được index vào ChromaDB")
    print(f"   Thư mục DB: {DB_PATH}")


# ─────────────────────────────────────────
# RETRIEVE
# ─────────────────────────────────────────

def retrieve(query: str, top_k=TOP_K) -> List[Dict[str, Any]]:
    import chromadb
    from sentence_transformers import SentenceTransformer

    embedder   = SentenceTransformer(EMBED_MODEL)
    client     = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_collection(COLLECTION)

    query_vec = embedder.encode([query])[0].tolist()
    results   = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for i, cid in enumerate(results["ids"][0]):
        # ChromaDB có thể trả text trực tiếp qua documents
        text = results["documents"][0][i] if results.get("documents") else ""
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i] if results.get("distances") else 0
        chunks.append({"text": text, "meta": meta, "distance": dist})

    return chunks


# ─────────────────────────────────────────
# GENERATE (Ollama)
# ─────────────────────────────────────────

def generate(query: str, context_chunks: list) -> str:
    import ollama

    # Ghép context
    context = "\n\n---\n\n".join(
        f"[{c['meta']['title']}] (độ liên quan: {1-c['distance']:.2f})\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""Bạn là trợ lý thông minh của Viện Vật lý (IOP), thuộc Viện Hàn lâm Khoa học và Công nghệ Việt Nam.
Hãy trả lời câu hỏi dựa trên thông tin được cung cấp bên dưới.
Nếu thông tin không đủ để trả lời, hãy nói rõ điều đó.
Trả lời bằng tiếng Việt, ngắn gọn và chính xác.
Khi nhắc đến tên người, hãy ghi đầy đủ học vị và tên.

=== THÔNG TIN THAM KHẢO ===
{context}

=== CÂU HỎI ===
{query}

=== TRẢ LỜI ==="""

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2},
    )
    return response["message"]["content"]


# ─────────────────────────────────────────
# MCP TOOLS — Thay thế time.json
# ─────────────────────────────────────────

def mcp_get_current_time(format_24h: bool = True) -> str:
    """Lấy giờ hiện tại. Dùng thay thế time.json."""
    now = datetime.now()
    if format_24h:
        return now.strftime("Bây giờ là %H giờ %M phút %S giây, ngày %d/%m/%Y.")
    else:
        return now.strftime("Bây giờ là %I giờ %M phút %S giây %p, ngày %d/%m/%Y.")


def mcp_get_current_date() -> str:
    """Lấy ngày hiện tại."""
    weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    now = datetime.now()
    wd = weekdays[now.weekday()]
    return f"Hôm nay là {wd}, ngày {now.day} tháng {now.month} năm {now.year}."


def mcp_get_day_of_week() -> str:
    """Lấy thứ trong tuần."""
    weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    return f"Hôm nay là {weekdays[datetime.now().weekday()]}."


# Routing: phát hiện câu hỏi về thời gian → gọi MCP tool trực tiếp
# Lưu ý: pattern phải đủ cụ thể để tránh false-positive với tên người / chức danh
#   ví dụ "Thứ trưởng", "thứ bảy", tên người có chữ "Thứ"...
_TIME_PATTERNS = [
    # Hỏi giờ
    r'mấy giờ', r'mấy giờ rồi', r'giờ hiện tại', r'thời gian hiện tại',
    r'bây giờ là mấy giờ', r'what time', r'current time',
    # Hỏi ngày
    r'ngày mấy', r'hôm nay ngày', r'ngày hiện tại', r'today.*date',
    r'what is.*date', r'current date',
    # Hỏi thứ trong tuần - phải có từ "thứ" đi kèm "mấy" hoặc "hôm nay"
    r'thứ mấy', r'hôm nay là thứ', r'hôm nay thứ mấy',
    r'what day is today', r'what day of week',
]

def _check_time_query(query: str) -> Optional[str]:
    """
    Kiểm tra xem query có phải câu hỏi về thời gian không.
    Nếu có → trả kết quả trực tiếp (không cần qua LLM).
    Nếu không → trả None để tiếp tục pipeline RAG.
    """
    q_lower = query.lower().strip()

    matched = False
    for pattern in _TIME_PATTERNS:
        if re.search(pattern, q_lower):
            matched = True
            break

    if not matched:
        return None

    # Phát hiện cụ thể: hỏi về thứ hay giờ hay ngày
    # Chỉ dùng cụm đủ cụ thể - KHÔNG match 'thứ' đứng một mình
    if any(kw in q_lower for kw in ['thứ mấy', 'hôm nay là thứ', 'hôm nay thứ mấy',
                                     'what day is today', 'what day of week']):
        return mcp_get_day_of_week()
    elif any(kw in q_lower for kw in ['ngày mấy', 'hôm nay ngày', 'ngày hiện tại',
                                      'date', 'current date']):
        return mcp_get_current_date()
    else:
        return mcp_get_current_time()


# ─────────────────────────────────────────
# QUERY (1 câu hỏi) — routing logic
# ─────────────────────────────────────────

def ask(query: str, verbose=False):
    print(f"\n🔍 Câu hỏi: {query}")

    # ── Bước 1: Kiểm tra time query (MCP tool) ──
    time_answer = _check_time_query(query)
    if time_answer:
        print("⏰ Phát hiện câu hỏi về thời gian → trả lời trực tiếp (MCP)")
        print(f"\n💬 Trả lời:\n{time_answer}")
        return time_answer

    # ── Bước 2: RAG pipeline ──
    chunks = retrieve(query)

    if verbose:
        print(f"\n📎 Context tìm được ({len(chunks)} chunks):")
        for c in chunks:
            print(f"  [{c['meta']['title']}] dist={c['distance']:.3f} | {c['text'][:80]}...")

    # ── Bước 3: Kiểm tra confidence ──
    if chunks and chunks[0]["distance"] > DISTANCE_THRESHOLD:
        print(f"\n⚠️  Độ liên quan thấp nhất: {chunks[0]['distance']:.3f} > {DISTANCE_THRESHOLD}")
        print("💬 Trả lời: Xin lỗi, tôi không có đủ thông tin để trả lời câu hỏi này.")
        return "Xin lỗi, tôi không có đủ thông tin để trả lời câu hỏi này."

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
    print("  IOP CHATBOT — Viện Vật lý (IOP-VAST)")
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
# MCP SERVER — standalone, chạy riêng
# ─────────────────────────────────────────

def run_mcp_server():
    """
    Chạy MCP server standalone.
    Cài đặt: pip install mcp
    Chạy: python LLM.py mcp-server
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("❌ Cần cài mcp: pip install mcp")
        return

    mcp = FastMCP("IOP-Tools", instructions="Công cụ cho IOP Chatbot — Viện Vật lý")

    @mcp.tool()
    def get_current_time(format_24h: bool = True) -> str:
        """Lấy giờ và ngày hiện tại. Dùng khi người hỏi mấy giờ, ngày mấy."""
        return mcp_get_current_time(format_24h)

    @mcp.tool()
    def get_current_date() -> str:
        """Lấy ngày hiện tại. Dùng khi người hỏi hôm nay ngày mấy."""
        return mcp_get_current_date()

    @mcp.tool()
    def get_day_of_week() -> str:
        """Lấy thứ trong tuần. Dùng khi người hỏi hôm nay thứ mấy."""
        return mcp_get_day_of_week()

    print("🚀 Khởi động MCP Server: IOP-Tools")
    print("   Tools: get_current_time, get_current_date, get_day_of_week")
    mcp.run()


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
            print("Usage: python LLM.py query <câu hỏi>")
        else:
            ask(q, verbose=True)
    elif cmd == "mcp-server":
        run_mcp_server()
    elif cmd == "test-time":
        # Quick test cho MCP tools
        print("=== Test MCP Tools ===")
        print(f"get_current_time(): {mcp_get_current_time()}")
        print(f"get_current_date(): {mcp_get_current_date()}")
        print(f"get_day_of_week():  {mcp_get_day_of_week()}")
        print(f"\nCheck 'mấy giờ rồi': {_check_time_query('mấy giờ rồi')}")
        print(f"Check 'hôm nay thứ mấy': {_check_time_query('hôm nay thứ mấy')}")
        print(f"Check 'viện trưởng là ai': {_check_time_query('viện trưởng là ai')}")
    else:
        print("Usage:")
        print("  python LLM.py build           # Build vector DB")
        print("  python LLM.py chat            # Chat với chatbot")
        print("  python LLM.py query <câu hỏi> # Hỏi 1 câu")
        print("  python LLM.py mcp-server      # Chạy MCP server")
        print("  python LLM.py test-time       # Test MCP time tools")
