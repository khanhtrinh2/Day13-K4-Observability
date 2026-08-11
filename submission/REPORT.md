# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: ChanTeam
- Repository URL: https://github.com/khanhtrinh2/Day13-K4-Observability.git
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
  - Baseline (CP0, trước khi làm TODO): **30/100** — 21 bản ghi; 20 record thiếu required field
    (`correlation_id` = `MISSING`), 20 record thiếu enrichment, 0 unique correlation ID.
    Lưu ý: mục PII scrubbing PASSED ngay từ baseline do `summarize_text()` đã scrub sẵn
    `message_preview`, chưa phải nhờ processor `scrub_event`.
  - Sau CP1: **100/100** — 21 bản ghi; 0 record thiếu required field, 0 record thiếu
    enrichment, 10 unique correlation ID, 0 PII leak.
    Evidence: [`evidence/correlation_id_evidence.txt`](evidence/correlation_id_evidence.txt).
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID: [`evidence/correlation_id_evidence.txt`](evidence/correlation_id_evidence.txt)
  — request `req-be5509e4` nối liền `request_received` → `response_sent` bằng cùng một ID.
  Middleware gán ID ở `app/middleware.py`, bind vào `structlog.contextvars` **trước** `call_next`
  nên mọi log phía sau tự mang ID mà không phải truyền tay; ID cũng được trả về client qua header
  `x-request-id` để người dùng báo lỗi kèm đúng ID cần tra.
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| A — Trịnh Bá Khánh Trình | CP1 Middleware: gán/propagate Correlation ID, enrich log context (`user_id_hash`, `session_id`, `feature`, `model`, `env`), exception handler cho 422/500 | PR `CP1/role-A` | Context phải bind **trước** `call_next` thì log sau mới thừa hưởng; `clear_contextvars()` là bắt buộc vì worker tái sử dụng context giữa các request. Handler của `Exception` nằm ngoài middleware (gắn vào `ServerErrorMiddleware`) nên phải tự set header `x-request-id`, nếu không response lỗi sẽ không truy vết được — đúng lúc cần nhất. |
| | | | |
