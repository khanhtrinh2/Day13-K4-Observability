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
  - Sau CP1:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID:
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
| | | | |
