import json
import os
import re
from typing import Any

from config import DATASET_PATH, DB_PATH, EMBED_MODEL
from .store import create_fresh_collection, get_embedder, reset_caches


def detect_record_type(content: str) -> str:
    if re.search(r"(\n|^)\d+\s+\S+.*(?:PGS|TS|ThS|GS|KS|Kỹ sư|Thạc sĩ)", content):
        return "nhan_su"
    if re.search(r"(?:doi|arXiv|tạp chí|Tạp chí|kỷ yếu|proceedings)", content, re.I):
        return "cong_bo"
    if len(content) < 800:
        return "ngan"
    return "van_ban"


def _chunk_nhan_su(content: str, title: str) -> list[str]:
    chunks: list[str] = []
    lines = content.strip().split("\n")
    header_lines: list[str] = []
    person_lines: list[str] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\s*\d+\s+", stripped):
            in_table = True
            person_lines.append(stripped)
        elif in_table:
            person_lines.append(stripped)
        else:
            header_lines.append(stripped)
    header_text = "\n".join(line for line in header_lines if line)
    if header_text:
        chunks.append(f"[{title}]\n{header_text}")
    center_name = title.replace(" - Nhân lực", "").replace(" - Nhân sự", "")
    for line in person_lines:
        if line:
            chunks.append(f"[{title}] {center_name} | {line}")
    return chunks or [f"[{title}]\n{content.strip()}"]


def _chunk_cong_bo(content: str, title: str) -> list[str]:
    chunks: list[str] = []
    current_item: list[str] = []
    for line in content.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            if current_item:
                text = "\n".join(current_item)
                if len(text) > 30:
                    chunks.append(f"[{title}]\n{text}")
                current_item = []
            continue
        if re.match(r"^[\d\-•▪▸●○◉]", stripped) or re.match(r"^\[\d{4}\]", stripped):
            if current_item:
                text = "\n".join(current_item)
                if len(text) > 30:
                    chunks.append(f"[{title}]\n{text}")
            current_item = [stripped]
        else:
            current_item.append(stripped)
    if current_item:
        text = "\n".join(current_item)
        if len(text) > 30:
            chunks.append(f"[{title}]\n{text}")
    return chunks or [f"[{title}]\n{content.strip()}"]


def _chunk_van_ban(content: str, title: str, max_size: int = 800) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", content.strip())
    chunks: list[str] = []
    current = f"[{title}]\n"
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= max_size:
            current += para + "\n\n"
        else:
            if len(current.strip()) > 50:
                chunks.append(current.strip())
            current = f"[{title}]\n{para}\n\n"
    if len(current.strip()) > 50:
        chunks.append(current.strip())
    return chunks or [f"[{title}]\n{content.strip()}"]


def smart_chunk(record: dict[str, Any]) -> list[str]:
    content = record["content"]
    title = record["title"]
    rtype = detect_record_type(content)
    if rtype == "nhan_su":
        return _chunk_nhan_su(content, title)
    if rtype == "cong_bo":
        return _chunk_cong_bo(content, title)
    if rtype == "ngan":
        return [f"[{title}]\n{content.strip()}"]
    return _chunk_van_ban(content, title)


def chunk_records(records: list[dict[str, Any]]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    texts: list[str] = []
    ids: list[str] = []
    metas: list[dict[str, Any]] = []
    for rec_idx, rec in enumerate(records):
        chunks = smart_chunk(rec)
        record_id = rec.get("id") or f"{rec.get('section', 'record')}-{rec_idx}"
        content_type = detect_record_type(rec.get("content", ""))
        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{record_id}-{chunk_idx}"
            texts.append(chunk)
            ids.append(chunk_id)
            metas.append(
                {
                    "chunk_id": chunk_id,
                    "record_id": record_id,
                    "title": rec.get("title", ""),
                    "section": rec.get("section", ""),
                    "content_type": content_type,
                    "source": "iop_dataset",
                    "url": rec.get("url", ""),
                }
            )
    return texts, ids, metas


def build_db(dataset_path=DATASET_PATH, db_path=DB_PATH, batch_size: int = 64, verbose: bool = True) -> int:
    reset_caches()
    if verbose:
        print("=" * 55)
        print("  BUILD IOP VECTOR DATABASE")
        print("=" * 55)
        print("\n📦 Đang load dataset...")
    with open(dataset_path, encoding="utf-8") as f:
        records = json.load(f)
    if verbose:
        print(f"   {len(records)} records")
        print(f"\n🔠 Đang load embedding model: {EMBED_MODEL}")
    allow_download = os.getenv("IVASTBOT_ALLOW_DOWNLOAD", "0") == "1"
    embedder = get_embedder(local_files_only=not allow_download)
    if verbose:
        print(f"\n🗄  Khởi tạo ChromaDB tại: {db_path}")
    collection = create_fresh_collection()
    all_chunks, all_ids, all_metas = chunk_records(records)
    if verbose:
        print("\n✂  Đang smart-chunk và embed...")
        print(f"   Tổng chunks: {len(all_chunks)}")
    for i in range(0, len(all_chunks), batch_size):
        batch_texts = all_chunks[i : i + batch_size]
        embeddings = embedder.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            documents=batch_texts,
            embeddings=embeddings,
            ids=all_ids[i : i + batch_size],
            metadatas=all_metas[i : i + batch_size],
        )
        if verbose and ((i // batch_size + 1) % 5 == 0 or i + batch_size >= len(all_chunks)):
            print(f"   Đã xử lý {min(i + batch_size, len(all_chunks))}/{len(all_chunks)} chunks")
    db_path.mkdir(parents=True, exist_ok=True)
    with open(db_path / "chunks_map.json", "w", encoding="utf-8") as f:
        json.dump(dict(zip(all_ids, all_chunks)), f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"\n✅ Build xong! {len(all_chunks)} chunks đã được index vào ChromaDB")
        print(f"   Thư mục DB: {db_path}")
    return len(all_chunks)
