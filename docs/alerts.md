# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: HighLatencyP95
- Severity: page
- SLI/SLO liên quan: `latency_p95_ms` (SLO: p95 < 3000ms, 99.5% trong cửa sổ 28 ngày — xem `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục trong 5 phút (tránh cảnh báo do một request đơn lẻ bị chậm)
- Ảnh hưởng tới người dùng: Người dùng chờ phản hồi lâu bất thường, trải nghiệm chat bị treo/timeout, có thể gây bỏ phiên (session drop-off)
- Ba bước kiểm tra đầu tiên:
  1. Xem panel `latency` trên dashboard (`config/dashboard.yaml`) để xác nhận p95/p99 đang vượt ngưỡng và từ thời điểm nào
  2. Mở trace của các request chậm gần nhất, xác định span nào chiếm phần lớn thời gian (thường là span retrieval/RAG hoặc gọi LLM)
  3. Kiểm tra `data/logs.jsonl` để tìm `correlation_id` của các request chậm, đối chiếu `feature`/`env` xem có tập trung vào một nhóm cụ thể không (ví dụ scenario `rag_slow`)
- Mitigation tạm thời:
  - Nếu do incident giả lập, tắt bằng `python scripts/inject_incident.py --scenario rag_slow --disable`
  - Nếu do tải cao, giảm tải bằng cách giới hạn concurrency hoặc bật timeout/fallback sớm cho bước retrieval chậm
- Owner: sre-oncall

## Alert 2

- Tên: HighErrorRate
- Severity: page
- SLI/SLO liên quan: `error_rate_pct` (SLO: < 2%, 99.0% trong cửa sổ 28 ngày — xem `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Một phần request bị lỗi, người dùng nhận response thất bại hoặc không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Xem panel `errors` trên dashboard để lấy `error_rate_pct` hiện tại và breakdown theo `error_type`
  2. Tra trace của các request lỗi để xác định span/tool nào raise exception (ví dụ tool call thất bại)
  3. Grep `data/logs.jsonl` theo `event == "request_failed"` và `error_type` để xác nhận lỗi tập trung vào một nguyên nhân cụ thể (ví dụ scenario `tool_fail`)
- Mitigation tạm thời:
  - Nếu do incident giả lập, tắt bằng `python scripts/inject_incident.py --scenario tool_fail --disable`
  - Nếu do dependency lỗi thật, bật circuit breaker/fallback cho tool đó hoặc rollback thay đổi gần nhất liên quan
- Owner: sre-oncall

## Alert 3

- Tên: DailyCostBudgetBurn
- Severity: ticket
- SLI/SLO liên quan: `daily_cost_usd` (SLO: <= $2.50/ngày — xem `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `daily_cost_usd > 2.5` liên tục trong 10 phút (đủ dài để loại trừ spike ngắn hạn)
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp trải nghiệm ngay lập tức, nhưng rủi ro vượt ngân sách vận hành và có thể dẫn tới việc bị giới hạn/tắt dịch vụ nếu không xử lý
- Ba bước kiểm tra đầu tiên:
  1. Xem panel `cost` và `tokens` trên dashboard để xác nhận chi phí và số token tăng bất thường so với `traffic`
  2. Đối chiếu `tokens_in`/`tokens_out` trung bình mỗi request trong `data/logs.jsonl`; nếu tăng đột biến trong khi traffic không đổi thì nghi ngờ prompt/response bị phình to
  3. Kiểm tra `prompt_name`/`prompt_version` trong trace để xem thay đổi prompt gần nhất có phải nguyên nhân (ví dụ scenario `cost_spike`)
- Mitigation tạm thời:
  - Nếu do incident giả lập, tắt bằng `python scripts/inject_incident.py --scenario cost_spike --disable`
  - Nếu do prompt/model thật gây tốn token, rollback prompt về version/label trước đó hoặc chuyển tạm sang model rẻ hơn
- Owner: sre-oncall
