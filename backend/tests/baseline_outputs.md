# Baseline Outputs

Date: 2026-06-29

## `python LLM.py build`

First sandboxed run failed because `SentenceTransformer` attempted a Hugging Face metadata request while network was restricted:

```text
Temporary failure in name resolution
RuntimeError: Cannot send a request, as the client has been closed.
```

After allowing network for the first model cache/build:

```text
BUILD IOP VECTOR DATABASE
39 records
Embedding model: paraphrase-multilingual-MiniLM-L12-v2
Tổng chunks: 139
Build xong! 139 chunks đã được index vào ChromaDB
DB: iop_chromadb
```

## `python LLM.py test-time`

```text
get_current_time(): Bây giờ là 12 giờ 34 phút 19 giây, ngày 29/06/2026.
get_current_date(): Hôm nay là Thứ Hai, ngày 29 tháng 6 năm 2026.
get_day_of_week(): Hôm nay là Thứ Hai.
Check 'mấy giờ rồi': Bây giờ là 12 giờ 34 phút 19 giây, ngày 29/06/2026.
Check 'hôm nay thứ mấy': Hôm nay là Thứ Hai.
Check 'viện trưởng là ai': None
```

## `python LLM.py query "hello"`

```text
Best retrieved distance: 0.713
Threshold: 0.55
Answer: Xin lỗi, tôi không có đủ thông tin để trả lời câu hỏi này.
```

## `python LLM.py query "giám đốc trung tâm vật lý lý thuyết là ai"`

```text
Top context:
- Vật lý lý thuyết - Nhân lực, dist=0.304
- Vật lý lý thuyết - Giới thiệu, dist=0.321

Answer:
Giám đốc Trung tâm Vật lý lý thuyết qua các thời kỳ là:
- Nhiệm kỳ 1982-1997: Đào Vọng Đức
- Nhiệm kỳ 1997-2003: Đoàn Nhật Quang
- Nhiệm kỳ 2003-2011: Nguyễn Hồng Quang
- Nhiệm kỳ 2011-2020: Hoàng Anh Tuấn
- Nhiệm kỳ 2020- đến nay: Trần Minh Tiến

Sources:
- https://iop.vast.vn/theor.php?l=0
- https://iop.vast.vn/theor.php?l=1
```

Review note: baseline RAG retrieves the right center, but the LLM expands the answer into historical directors. A deterministic member lookup route is needed for current role/member questions.

