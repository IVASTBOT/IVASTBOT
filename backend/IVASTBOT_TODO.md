# IVASTBOT TODO & Implementation Plan

> Mục tiêu: hoàn thiện Brain AI harness, RAG pipeline, và khung Computer Vision cho nhận diện/tham chiếu thông tin thành viên Viện Vật lý IOP-VAST. Hệ thống ưu tiên local-first, có thể chạy offline sau setup, dễ fine-tuning/mở rộng dữ liệu về sau.

---

## 1. Nguyên tắc triển khai

- Không rewrite toàn bộ nếu `backend/LLM.py` đang chạy được; ưu tiên refactor từng phần có adapter để giữ compatibility.
- Mọi model/resource nặng phải lazy-load + cache một lần, không load lại mỗi request.
- RAG phải có confidence threshold, citation/source chunk, và câu trả lời “không có thông tin” khi context không đủ.
- Computer Vision chỉ nhận diện/đối chiếu với thành viên đã được đăng ký dữ liệu và có quyền sử dụng ảnh. Người lạ phải trả `unknown`.
- Chưa cần fine-tune ngay; trước mắt tạo harness, schema, folder, endpoint, CLI và TODO để sau này thêm ảnh/dữ liệu.
- Tất cả phải có test tối thiểu và lệnh chạy rõ ràng.

---

## 2. Kiến trúc target

```text
backend/
├── LLM.py                         # Giữ CLI cũ: build/chat/query/test-time/mcp-server
├── app/
│   ├── main.py                    # FastAPI entrypoint
│   ├── schemas.py                 # Request/response schemas chung
│   └── deps.py                    # Shared dependencies/cache
├── brain/
│   ├── harness.py                 # Orchestrator chính: route FRL/RAG/member/CV/tool
│   ├── router.py                  # Intent routing
│   ├── response.py                # Chuẩn hóa response
│   └── logging.py                 # Query logs/eval logs
├── rag/
│   ├── ingest.py                  # Load dataset + smart chunking
│   ├── store.py                   # Chroma collection/cache
│   ├── retriever.py               # Retrieve + threshold + optional rerank
│   ├── generator.py               # Prompt LLM + citations
│   └── eval.py                    # RAG test harness
├── members/
│   ├── members.schema.json        # Schema metadata thành viên
│   ├── members.jsonl              # Dữ liệu thành viên thêm sau
│   ├── resolver.py                # Entity matching theo tên/alias/khoa/phòng ban
│   └── tool.py                    # Member lookup tool/MCP-compatible
├── vision/
│   ├── cv_service.py              # Entry service cho ảnh
│   ├── enrollment.py              # Tạo/cập nhật embedding ảnh thành viên
│   ├── recognizer.py              # So khớp embedding, threshold, unknown fallback
│   ├── ocr.py                     # OCR name-card/profile image nếu dùng
│   └── README.md                  # Cách thêm ảnh/fine-tuning sau
├── RAG/database/FRL/
│   ├── iop_dataset.json
│   ├── iop_dataset.jsonl
│   ├── IOP-info.json
│   ├── model-inf.json
│   └── members-inf/
│       ├── members.jsonl
│       ├── images/                # Ảnh raw, optional/local-only
│       ├── embeddings/            # Vector nhận diện đã build
│       └── TODO.md                # Việc cần làm cho tuning/data
└── tests/
    ├── test_brain_router.py
    ├── test_rag_retrieval.py
    ├── test_members_resolver.py
    └── test_vision_harness.py
```

---

## 3. Phase 1 — Review baseline hiện tại

- [ ] Xác định repo thật đang dùng: `/home/z/my-project/download/iop-rag/backend/` hay `~/workspace/project/IVASTBOT_WS/backend/`.
- [ ] Chạy lại các lệnh baseline:

```bash
python LLM.py build
python LLM.py test-time
python LLM.py query "giám đốc trung tâm vật lý lý thuyết là ai"
python LLM.py query "hello"
```

- [ ] Ghi nhận output hiện tại vào `tests/baseline_outputs.md`.
- [ ] Đảm bảo không phá các lệnh CLI cũ.
- [ ] Kiểm tra cache model, Chroma collection, Ollama client.
- [ ] Kiểm tra threshold hiện tại `DISTANCE_THRESHOLD = 0.55`.

Definition of Done:

- CLI cũ vẫn chạy.
- Build DB thành công.
- Query ngoài domain trả “không có thông tin”.
- Query đúng domain có retrieval distance hợp lý và sinh câu trả lời.

---

## 4. Phase 2 — Brain AI harness

Mục tiêu: tạo một lớp điều phối thống nhất thay vì mọi logic nằm rải trong `LLM.py`.

- [ ] Tạo `brain/harness.py` với class `BrainHarness`.
- [ ] Chuẩn hóa input:

```python
class BrainRequest(BaseModel):
    text: str | None = None
    image_path: str | None = None
    session_id: str | None = None
    mode: Literal["auto", "rag", "member", "vision", "time"] = "auto"
```

- [ ] Chuẩn hóa output:

```python
class BrainResponse(BaseModel):
    answer: str
    route: str
    confidence: float | None = None
    sources: list[dict] = []
    metadata: dict = {}
```

- [ ] Router route theo thứ tự:
  1. Time/Date query → MCP time tools
  2. Identity/static FRL → fixed response
  3. Member query rõ ràng → member resolver
  4. Image input → vision service
  5. Còn lại → RAG
- [ ] Thêm log JSONL cho mỗi request:

```json
{"timestamp":"...","query":"...","route":"rag","confidence":0.72,"latency_ms":1234}
```

- [ ] Giữ adapter để `LLM.py query/chat` gọi được `BrainHarness`.

Definition of Done:

- Có thể gọi cùng logic qua CLI và FastAPI.
- Có response schema thống nhất.
- Có logs phục vụ debug/eval.
- Không load lại model mỗi request.

---

## 5. Phase 3 — Hoàn thiện RAG

- [ ] Tách smart chunking từ `LLM.py` sang `rag/ingest.py` nhưng vẫn giữ import compatibility.
- [ ] Mỗi chunk phải có metadata:

```json
{
  "chunk_id": "...",
  "record_id": "...",
  "title": "...",
  "section": "...",
  "content_type": "nhan_su|cong_bo|ngan|dai",
  "source": "iop_dataset.json",
  "url": null
}
```

- [ ] Retriever trả về:
  - text chunk
  - distance
  - similarity/confidence quy đổi
  - metadata/source
- [ ] Generator bắt buộc chỉ trả lời từ context.
- [ ] Prompt RAG cần có rule:
  - Không bịa.
  - Không có thông tin thì nói không có thông tin trong dữ liệu hiện tại.
  - Trả lời tiếng Việt tự nhiên.
  - Với câu hỏi về nhân sự, ưu tiên nêu họ tên, chức danh, đơn vị.
- [ ] Thêm `rag/eval.py` với test set tối thiểu 20 câu:
  - 10 câu đúng domain
  - 5 câu nhân sự
  - 5 câu ngoài domain
- [ ] Log retrieval top-k để debug.

Definition of Done:

- `python LLM.py build` vẫn build được 130+ chunks.
- `python -m rag.eval` chạy được.
- Có file eval report JSON/Markdown.
- Query ngoài domain không hallucinate.
- Query đúng domain có source/citation metadata.

---

## 6. Phase 4 — Member information lookup

Mục tiêu: thành viên IOP không nên phụ thuộc hoàn toàn vào vector search. Cần lookup table riêng.

- [ ] Tạo schema `members/members.schema.json`.
- [ ] Tạo file dữ liệu ban đầu `RAG/database/FRL/members-inf/members.jsonl`.
- [ ] Mỗi member dùng schema:

```json
{
  "member_id": "iop_member_001",
  "full_name": "",
  "aliases": [],
  "title": "",
  "position": "",
  "department": "",
  "email": "",
  "phone": "",
  "office": "",
  "research_interests": [],
  "profile_url": "",
  "image_paths": [],
  "consent_for_vision": false,
  "notes": ""
}
```

- [ ] Implement `members/resolver.py`:
  - normalize Vietnamese text
  - fuzzy match tên/alias
  - match theo department/position
  - trả top candidates + confidence
- [ ] Implement member tool:

```python
def lookup_member(query: str) -> dict:
    ...
```

- [ ] Nếu không đủ confidence → fallback RAG hoặc trả không chắc chắn.

Definition of Done:

- Hỏi “ai là giám đốc trung tâm X?” có thể trả từ member table nếu có dữ liệu.
- Hỏi tên gần đúng vẫn tìm được alias.
- Không tìm thấy thì không bịa.

---

## 7. Phase 5 — Computer Vision harness cho nhận diện/tham chiếu thành viên

Mục tiêu trước mắt: hoàn thiện khung chạy được, chưa cần accuracy cao vì ảnh/dữ liệu fine-tuning sẽ thêm sau.

### 7.1 Scope an toàn

- Chỉ nhận diện thành viên đã được enroll trong local database.
- Chỉ dùng ảnh có quyền sử dụng/được đồng ý.
- Nếu confidence thấp, trả `unknown`, không đoán danh tính.
- Không cần lưu raw image trong production nếu không bật debug/enrollment mode.

### 7.2 Chức năng cần có

- [ ] Endpoint/CLI nhận ảnh:

```bash
python LLM.py vision-query path/to/image.jpg
python LLM.py enroll-member --member-id iop_member_001 --image path/to/photo.jpg
```

- [ ] API:

```http
POST /vision/recognize
POST /vision/enroll
```

- [ ] `vision/cv_service.py` nhận image path/upload và trả:

```json
{
  "status": "ok|unknown|error",
  "member_id": "...",
  "confidence": 0.0,
  "matched_member": {},
  "message": ""
}
```

- [ ] `vision/recognizer.py` có interface model-agnostic:

```python
class VisionRecognizer:
    def enroll(self, member_id: str, image_path: str) -> dict: ...
    def recognize(self, image_path: str) -> dict: ...
```

- [ ] Giai đoạn đầu có thể dùng placeholder/local embedding:
  - Ưu tiên thiết kế interface sạch.
  - Cho phép thay backend bằng face embedding model sau.
  - Có threshold `VISION_DISTANCE_THRESHOLD`.
- [ ] OCR optional:
  - Nếu ảnh là thẻ tên/profile screenshot, trích text rồi gọi `lookup_member(text)`.
  - OCR không bắt buộc ở MVP nếu chưa có dependency.

Definition of Done:

- Có thể enroll một member bằng ảnh test.
- Có thể query lại ảnh test và trả candidate hoặc unknown.
- Có test với ảnh giả/fixture.
- Không crash khi ảnh không hợp lệ.
- Có TODO rõ để fine-tuning/thêm model sau.

---

## 8. Phase 6 — FastAPI integration

- [ ] Tạo `app/main.py`.
- [ ] Endpoints:

```http
GET  /health
POST /chat
POST /rag/query
POST /members/lookup
POST /vision/recognize
POST /vision/enroll
```

- [ ] `/chat` gọi `BrainHarness(mode="auto")`.
- [ ] `/rag/query` ép route RAG.
- [ ] `/members/lookup` ép route member.
- [ ] `/vision/recognize` nhận upload image.
- [ ] Startup event warmup optional:
  - Chroma collection
  - embedder
  - Ollama client check

Definition of Done:

- Chạy được:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `/health` trả status OK.
- `/chat` trả answer/schema thống nhất.

---

## 9. Phase 7 — Test harness & quality gate

- [ ] Unit tests:
  - router time false-positive
  - RAG threshold
  - member resolver fuzzy matching
  - vision unknown fallback
- [ ] Integration tests:
  - build DB
  - query domain
  - query out-of-domain
  - member lookup
  - vision enroll/recognize fixture
- [ ] Eval report:

```bash
python -m rag.eval --out reports/rag_eval.md
pytest -q
```

Definition of Done:

- Test pass.
- Có report rõ câu nào pass/fail.
- Các command trong README chạy được.

---

## 10. Fine-tuning / data TODO cho sau

Ghi các việc này vào `RAG/database/FRL/members-inf/TODO.md`:

- [ ] Crawl/nhập danh sách thành viên đầy đủ từ website IOP-VAST.
- [ ] Chuẩn hóa tên tiếng Việt, học hàm/học vị, chức vụ, phòng ban.
- [ ] Thêm alias cho từng người: không dấu, viết tắt, tên thường gọi.
- [ ] Thu thập ảnh profile có quyền sử dụng.
- [ ] Đánh dấu `consent_for_vision=true` cho người được enroll.
- [ ] Tạo ít nhất 3-5 ảnh/member nếu muốn nhận diện ổn hơn.
- [ ] Build face/image embeddings.
- [ ] Tạo validation set riêng, không trùng ảnh enroll.
- [ ] Đánh giá false accept/false reject.
- [ ] Chỉnh `VISION_DISTANCE_THRESHOLD` theo validation set.
- [ ] Nếu cần fine-tune model, tạo script riêng và lưu experiment metadata.

---

# Coding Agent Prompt

Dùng prompt dưới đây để giao việc cho coding agent trong repo.

```text
Bạn là senior backend engineer kiêm ML/RAG engineer. Hãy review và hoàn thiện project IVASTBOT/IOP RAG chatbot local-first cho Viện Vật lý IOP-VAST.

Context hiện tại:
- Backend Python, Ubuntu, package manager uv.
- Project có file chính backend/LLM.py đã chạy được.
- Hệ thống dùng Ollama + ChromaDB + SentenceTransformer.
- Embedding model: paraphrase-multilingual-MiniLM-L12-v2.
- LLM hiện có/fallback: qwen2.5:3b qua Ollama. Có thể cấu hình qwen3.5:latest nếu local machine đã pull model.
- Dataset nằm trong RAG/database/FRL/ gồm iop_dataset.json, iop_dataset.jsonl, IOP-info.json, model-inf.json, members-inf/.
- Smart chunking hiện có: nhân sự mỗi người một chunk, công bố mỗi bài một chunk, văn bản ngắn giữ nguyên, văn bản dài chia theo đoạn, prepend title vào chunk.
- DB hiện build ra khoảng 130 chunks từ 39 records.
- Có MCP time tools và routing tránh false-positive như “thứ trưởng”.
- Có lazy cache cho SentenceTransformer, Chroma collection, Ollama client.
- Có DISTANCE_THRESHOLD = 0.55 để chống hallucination.

Mục tiêu:
1. Review baseline, không phá CLI cũ.
2. Thêm Brain AI harness/orchestrator để route query qua FRL/time/member/vision/RAG.
3. Hoàn thiện RAG thành module rõ ràng, có metadata source/citation, eval harness, threshold, logging.
4. Thêm member information lookup riêng, không phụ thuộc hoàn toàn vào vector search.
5. Thêm Computer Vision harness cho nhận diện/tham chiếu thành viên IOP. Trước mắt hoàn thiện interface, schema, endpoint, CLI, placeholder model/embedding cũng được. Dữ liệu ảnh và fine-tuning sẽ thêm sau.
6. Tạo TODO.md cho phần data/fine-tuning thành viên và vision.
7. Thêm FastAPI endpoints và test tối thiểu.

Ràng buộc quan trọng:
- Không rewrite toàn bộ nếu không cần. Ưu tiên refactor an toàn và giữ backward compatibility.
- Không dùng internet runtime sau setup.
- Không load lại model nặng mỗi request.
- Không hallucinate. Nếu retrieval/member/vision confidence thấp, trả unknown/không có thông tin.
- Computer Vision chỉ nhận diện người đã enroll và có consent_for_vision=true. Không đoán danh tính người lạ.
- Code phải chạy local.
- Mọi thay đổi phải có command test rõ ràng.

Việc cần làm chi tiết:

A. Baseline review
- Tìm đúng backend root.
- Chạy/kiểm tra: python LLM.py build, python LLM.py test-time, python LLM.py query "hello", python LLM.py query "giám đốc trung tâm vật lý lý thuyết là ai".
- Ghi chú output quan trọng vào tests/baseline_outputs.md.

B. Brain harness
- Tạo brain/harness.py, brain/router.py, brain/response.py.
- Tạo schemas BrainRequest và BrainResponse.
- Router ưu tiên: time/date -> fixed response -> member lookup -> vision nếu có image -> RAG.
- LLM.py phải gọi BrainHarness cho chat/query nhưng CLI cũ vẫn dùng được.
- Log mỗi request ra JSONL.

C. RAG module
- Tách ingest/store/retriever/generator/eval nếu có thể.
- Mỗi chunk phải có chunk_id, record_id, title, section, content_type, source, url.
- Retriever trả top_k gồm text, distance, confidence, metadata.
- Nếu best distance > DISTANCE_THRESHOLD thì từ chối trả lời.
- Generator prompt phải chỉ dùng context, trả lời tiếng Việt, có thông tin nguồn/citation metadata.
- Thêm rag/eval.py với test set tối thiểu.

D. Member lookup
- Tạo RAG/database/FRL/members-inf/members.jsonl nếu chưa có.
- Tạo members/members.schema.json.
- Tạo members/resolver.py có normalize tiếng Việt, alias matching, fuzzy matching.
- Tạo lookup_member(query: str) -> dict.
- Nếu member confidence thấp, không bịa.

E. Computer Vision harness
- Tạo vision/cv_service.py, vision/enrollment.py, vision/recognizer.py, vision/README.md.
- Tạo interface VisionRecognizer với enroll() và recognize().
- Trước mắt cho phép dùng placeholder/simple embedding backend để flow chạy được; thiết kế sao cho thay bằng face/image embedding model sau dễ dàng.
- Dữ liệu đặt trong RAG/database/FRL/members-inf/images/ và embeddings/.
- Chỉ match member có consent_for_vision=true.
- Nếu confidence thấp hoặc không có embedding, trả status unknown.
- Thêm CLI:
  python LLM.py enroll-member --member-id <id> --image <path>
  python LLM.py vision-query <image_path>
- Thêm API endpoints POST /vision/enroll và POST /vision/recognize.

F. FastAPI
- Tạo app/main.py.
- Endpoints: GET /health, POST /chat, POST /rag/query, POST /members/lookup, POST /vision/recognize, POST /vision/enroll.
- /chat dùng BrainHarness auto mode.

G. Tests
- Thêm pytest cho router, RAG threshold, member resolver, vision unknown fallback.
- Commands cuối cùng phải chạy:
  python LLM.py build
  python LLM.py test-time
  python LLM.py query "hello"
  python LLM.py query "giám đốc trung tâm vật lý lý thuyết là ai"
  python LLM.py vision-query tests/fixtures/member_test.jpg
  pytest -q
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Deliverables:
- Code patch/refactor hoàn chỉnh.
- TODO.md cho members-inf/fine-tuning.
- README hoặc phần hướng dẫn lệnh chạy.
- Không để broken imports.
- Nếu thiếu dependency/model/ảnh thật thì tạo fallback rõ ràng và ghi TODO, nhưng flow chính vẫn chạy được.
```

---

## 11. Acceptance checklist cuối cùng

- [ ] CLI cũ không vỡ.
- [ ] RAG build/query chạy.
- [ ] BrainHarness route được các mode chính.
- [ ] Member lookup có schema và file dữ liệu.
- [ ] Vision harness có enroll/recognize interface.
- [ ] Unknown fallback hoạt động cho ảnh/người chưa enroll.
- [ ] FastAPI có `/health` và `/chat`.
- [ ] Có tests cơ bản.
- [ ] Có TODO.md cho phần tuning/data sau.
- [ ] Không hallucinate khi thiếu dữ liệu.