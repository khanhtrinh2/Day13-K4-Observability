# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: ChanTeam
- Repository URL: https://github.com/khanhtrinh2/Day13-K4-Observability.git
- Commit SHA cuối:
- Thành viên và vai trò:

| Mã | Họ tên | MSSV | Vai trò |
|---|---|---|---|
| A | Trịnh Bá Khánh Trình | | API & Middleware |
| B | Nguyễn Hoàng Đạt | 2A202601460 | Security Engineer |
| C | Nguyễn Hữu Tuyến | 2A202601520 | Metrics & Dashboard |
| D | Nguyễn Văn Phúc | 2A202601350 | SRE & Alerts Engineer |
| E | Vũ Thành Khang | 2A202601866 | QA & Chief Investigator |

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
| A — Trịnh Bá Khánh Trình | CP1 Middleware: gán/propagate Correlation ID, enrich log context (`user_id_hash`, `session_id`, `feature`, `model`, `env`), exception handler cho 422/500 | [PR #4](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/4) (`f0d28e0`), [PR #5](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/5) (`91cf51b`), [PR #1](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/1) (`9e7f153`) | Context phải bind **trước** `call_next` thì log sau mới thừa hưởng; `clear_contextvars()` là bắt buộc vì worker tái sử dụng context giữa các request. Handler của `Exception` nằm ngoài middleware (gắn vào `ServerErrorMiddleware`) nên phải tự set header `x-request-id`, nếu không response lỗi sẽ không truy vết được — đúng lúc cần nhất. Bài học thứ hai: enrichment từng bị mất khi merge nhánh khác (`c6aa5e8`) mà không ai phát hiện, chỉ có test tự viết bắt được — nên test là thứ bảo vệ phần việc của mình. |
| B — Nguyễn Hoàng Đạt (2A202601460) | CP1 PII Scrubbing: thêm regex patterns (passport, địa chỉ VN), bật processor `scrub_event` trong chain logging, kiểm chứng log không lộ PII | [PR #2](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/2) (`bc86eb3`) | _(tự điền)_ |
| C — Nguyễn Hữu Tuyến (2A202601520) | Triển khai `error_rate_pct` theo tổng số request, thiết kế dashboard 6 nhóm chỉ số (latency, traffic, errors, cost, tokens, quality), viết test và validator | `8bd03d2` — commit đẩy thẳng lên `main`, chưa qua PR | _(tự điền)_ |
| D — Nguyễn Văn Phúc (2A202601350) | CP2: thiết lập SLO, viết Alert rules và Alert Runbook xử lý sự cố | [PR #3](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/3) (`7e75441`) | _(tự điền)_ |
| E — Vũ Thành Khang (2A202601866) | Chạy load test, bọc trace cho sub-component RAG/LLM (phần mở rộng), dẫn dắt điều tra Challenge (CP3), hoàn thiện báo cáo nhóm | [PR #6](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/6) (`e6c7b7c`, `c6aa5e8`) | _(tự điền)_ |
