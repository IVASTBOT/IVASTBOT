## 🤖 Giới thiệu

**IVASTBOT** là chatbot hỏi-đáp tiếng Việt theo kiến trúc **RAG (Retrieval-Augmented Generation)**, phát triển cho **Viện Vật lý – Viện Hàn lâm Khoa học và Công nghệ Việt Nam (IOP-VAST)**. Mục tiêu của bot là trả lời các câu hỏi về thông tin của Viện (giới thiệu, cơ cấu tổ chức, nhân lực, các trung tâm/phòng, đề tài nghiên cứu, công bố khoa học...) dựa trên dữ liệu được thu thập từ website chính thức của Viện.

## 🧠 Kiến trúc & Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend API | FastAPI |
| LLM (sinh câu trả lời) | Ollama – `qwen2.5:7b` |
| Vector database | ChromaDB |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` |
| Kiến trúc xử lý | Hybrid FRL + RAG |
| Quản lý package | `uv` |
| Môi trường | Ubuntu (Linux) |

> _Cập nhật bảng này nếu có thêm thư viện/frontend mới (vd: React, LangChain, v.v.)_

## 👥 Thành viên nhóm

| Vai trò | Họ tên | Phụ trách |
|---|---|---|
| Backend Lead (Brain LLM)| **Nguyễn Gia Bảo, Trần Binh Minh, ** | "Bộ não" của hệ thống – pipeline RAG (scraping → làm sạch dữ liệu → embedding → ChromaDB), tích hợp LLM qua Ollama, xây API bằng FastAPI |
|Embedding | **** | Trọng trách xử lý và làm sạch dữ liệu, xây dựng hệ thống embedding và lưu trữ vào ChromaDB |
,...

> _Các thành viên vui lòng tự bổ sung tên + vai trò của mình vào bảng trên._

## ⚙️ Hướng dẫn cài đặt (sau khi clone/pull)

```bash
# 1. Tạo virtual environment & cài dependency
uv venv
uv sync   # hoặc: uv pip install -r requirements.txt

# 2. Tải model LLM về (chạy lần đầu, có thể mất thời gian)
ollama pull qwen2.5:7b

# 3. Tạo file môi trường từ mẫu
cp .env.example .env
# -> điền các giá trị cần thiết vào .env

# 4. Build lại ChromaDB từ dữ liệu (KHÔNG commit thư mục db này)
python scripts/build_db.py   # cập nhật đúng tên script thực tế
```

## ⚠️ Lưu ý quan trọng cho thành viên

- **KHÔNG commit** các thư mục/file sau (đã có trong `.gitignore`): `.venv/`, `__pycache__/`, dữ liệu ChromaDB (`chroma_db/`, `db/`...), model weight đã tải về, file `.env`, log.
- Sau mỗi lần `git pull`, nếu có thay đổi về `pyproject.toml`/`requirements.txt`, chạy lại `uv sync` để đồng bộ thư viện.
- Dữ liệu ChromaDB được **build lại từ script**, không phải tải về — nếu thay đổi dữ liệu nguồn (dataset scrape), cần chạy lại `scripts/build_db.py`.
- Nếu thêm thư viện mới, nhớ cập nhật `pyproject.toml`/`requirements.txt` và bảng "Công nghệ sử dụng" ở trên.
- Trước khi push, kiểm tra `git status` để chắc không lỡ add file nặng (venv, model, db...).
- Đặt tên branch theo quy ước: `feature/<tên-tính-năng>`, `fix/<mô-tả-lỗi>` (cập nhật nếu team có quy ước khác).