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
  - Sau CP3 (đo lại trên bộ log của challenge): **100/100** — 23 bản ghi, 12 unique correlation
    ID, 0 record thiếu required field, 0 record thiếu enrichment, 0 PII leak.
- Tổng số traces: **34** trên Langfuse Cloud (project `My Project`), vượt yêu cầu tối thiểu 10.
  Ảnh: [`evidence/langfuse_traces_overview.png`](evidence/langfuse_traces_overview.png) — chụp
  lúc 17:02 khi mới có 20 traces và 40 observations; con số 34 là tổng sau khi chạy thêm
  phần prompt versioning (CP2) và challenge (CP3).
- Số PII leak còn lại: **0** — `validate_logs.py` báo `Potential PII leaks detected: 0` trên
  23 bản ghi; đã kiểm tra thủ công thêm với email, số điện thoại VN và số thẻ test.
- Link/đường dẫn dashboard: contract tại [`config/dashboard.yaml`](../config/dashboard.yaml),
  nguồn dữ liệu là `data/logs.jsonl`. `python scripts/validate_dashboard.py` →
  `HỢP LỆ: 6/6 panel có trong dashboard contract.`

## 3. Logging và tracing

- Evidence correlation ID: [`evidence/correlation_id_evidence.txt`](evidence/correlation_id_evidence.txt)
  — request `req-be5509e4` nối liền `request_received` → `response_sent` bằng cùng một ID.
  Middleware gán ID ở `app/middleware.py`, bind vào `structlog.contextvars` **trước** `call_next`
  nên mọi log phía sau tự mang ID mà không phải truyền tay; ID cũng được trả về client qua header
  `x-request-id` để người dùng báo lỗi kèm đúng ID cần tra.
- Evidence PII redaction: [`evidence/pii_redaction_evidence.txt`](evidence/pii_redaction_evidence.txt)
  và [`evidence/test_pii_result.txt`](evidence/test_pii_result.txt).
- Evidence trace waterfall: trace `7a12658006ca57379d4fe4bff6176823` (lúc có incident) so với
  `8bdf023e34a6eaaaa3a3b65e9963fd99` (lúc khoẻ mạnh), cùng `session_id = k4-challenge-s01`.
  Chi tiết trong [`evidence/challenge_investigation.md`](evidence/challenge_investigation.md),
  ảnh waterfall tại [`evidence/trace_waterfall.png`](evidence/trace_waterfall.png).

  ```
  trace 7a12658006ca...        start(+ms)   duration(ms)
  run                                   0           2652
  rag.retrieve                          0           2500
  llm.generate                       2500            151
  ```

- Giải thích một span đáng chú ý: span **`rag.retrieve`** chiếm **2500/2652 ms = 94%** tổng
  thời gian request khi incident bật, trong khi span `llm.generate` giữ nguyên 151 ms ở cả hai
  pha. Chính sự tương phản này loại trừ LLM khỏi diện nghi vấn và chỉ thẳng vào tầng retrieval —
  điều mà metrics tổng hợp không thể nói được, vì metrics chỉ thấy "request chậm". Nếu không
  tách span riêng cho từng sub-component thì trace chỉ hiện `run = 2652 ms` và việc điều tra
  sẽ phải đoán.

## 4. Prompt versioning

- Prompt name: `day13-chat` (text prompt, giữ nguyên 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`
  theo contract trong [`docs/PROMPT_VERSIONING.md`](../docs/PROMPT_VERSIONING.md)).
- Version/label baseline: **version 1**, labels `baseline` + `production`. Nội dung là template
  gốc `DEFAULT_PROMPT_TEMPLATE` trong `app/prompt_management.py`.
- Version/label candidate: **version 2**, label `candidate`. Thay đổi nhỏ: thêm ràng buộc
  *"Answer in at most 3 sentences. Cite the retrieved docs when they are relevant."*
- Trace ID của mỗi version:

  | Bước | Label dùng | Version resolve được | Trace ID |
  |---|---|---|---|
  | Chạy với baseline | `baseline` | v1 | `64a33bc0686fb44aa8bd2a22dc88493c` |
  | Chạy với candidate | `candidate` | v2 | `57cabc526bb667bbdefece8621f1c147` |
  | Sau khi promote | `production` | **v2** | `14f79347a832e7de05762444193439cc` |
  | Sau khi rollback | `production` | **v1** | `8ecf553d498e05380cf0e682e894a777` |

  Cả 4 lần chạy dùng **cùng một input** (`"Explain why metrics traces and logs work together."`)
  để khác biệt duy nhất đến từ prompt version.

  Ảnh danh sách hai version: [`evidence/prompt_versions.png`](evidence/prompt_versions.png).

- Bằng chứng đổi label hoặc rollback: dùng `client.update_prompt(name="day13-chat", version=N,
  new_labels=["production"])`, và xác nhận lại bằng `client.get_prompt(..., cache_ttl_seconds=0)`
  sau mỗi bước:

  ```
  TRUOC        : production -> version 1
  SAU PROMOTE  : production -> version 2
  SAU ROLLBACK : production -> version 1
  ```

  Trace `14f79347...` chạy khi `production` đang trỏ v2, trace `8ecf553d...` chạy sau khi đã
  rollback về v1 — hai trace này là bằng chứng rollback có hiệu lực thật ở tầng runtime, không
  chỉ đổi nhãn trên giao diện.

  Ảnh nhãn `production` sau khi rollback về v1:
  [`evidence/prompt_rollback.png`](evidence/prompt_rollback.png).

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
  Kết xuất đầy đủ của cả ba lệnh kiểm tra:
  [`evidence/validator_results.txt`](evidence/validator_results.txt).
- Evidence dashboard: contract tại [`config/dashboard.yaml`](../config/dashboard.yaml) — 6 panel
  `latency`, `traffic`, `errors`, `cost`, `tokens`, `quality`; time range 60 phút, refresh 30s,
  mỗi panel có `unit` và `threshold` riêng.

  Dashboard runtime dựng bằng Streamlit tại [`scripts/dashboard_app.py`](../scripts/dashboard_app.py),
  đọc trực tiếp `data/logs.jsonl` đúng như `docs/DASHBOARD_SETUP.md` quy định:

  ```bash
  streamlit run scripts/dashboard_app.py
  ```

  Mọi ngưỡng và đơn vị được **đọc từ `config/dashboard.yaml`** chứ không hard-code, nên
  contract là nguồn chuẩn duy nhất — sửa YAML thì dashboard đổi theo. Mỗi panel hiển thị
  trạng thái ĐẠT/VI PHẠM so với threshold của chính nó, và hai panel latency/quality có
  đường SLO nét đứt. Bảng dữ liệu thô nằm trong expander cuối trang để không phải đọc
  bằng màu.

  Kiểm chứng bằng `tests/test_dashboard_app.py` (7 test, dùng `streamlit.testing.v1.AppTest`):
  render đủ 6 panel không exception, không có log vẫn cảnh báo thay vì crash, và ngưỡng
  của mỗi panel phải trỏ vào một phép tổng hợp mà panel thực sự tính.

  Ảnh: [`evidence/dashboard_6_panels.png`](evidence/dashboard_6_panels.png).
- SLO đã chọn và lý do: xem [`config/slo.yaml`](../config/slo.yaml). Bốn SLI được chọn để mỗi
  loại incident trong `app/incidents.py` đều có ít nhất một chỉ số bắt được:
  `latency_p95_ms ≤ 3000` (bắt `rag_slow`), `error_rate_pct ≤ 2` (bắt `tool_fail`),
  `daily_cost_usd ≤ 2.5` (bắt `cost_spike`), `quality_score_avg ≥ 0.75`.
- Alert rules và runbook: 3 alert trong [`config/alert_rules.yaml`](../config/alert_rules.yaml)
  (`HighLatencyP95`, `HighErrorRate`, `DailyCostBudgetBurn`), runbook tại
  [`docs/alerts.md`](../docs/alerts.md).

### Khoảng trống phát hiện được khi chạy challenge thật

Incident `rag_slow` đẩy `latency_p95` lên **2682 ms** và giữ `error_rate_pct` ở **0%**.
Đối chiếu với 3 alert đang cấu hình:

| Alert | Điều kiện | Giá trị thực tế | Có kêu không? |
|---|---|---|---|
| `HighLatencyP95` | `latency_p95_ms > 3000 for 5m` | 2682 ms | **Không** |
| `HighErrorRate` | `error_rate_pct > 2 for 5m` | 0% | **Không** |
| `DailyCostBudgetBurn` | `daily_cost_usd > 2.5 for 10m` | $0.02 | **Không** |

Nghĩa là bộ alert hiện tại **để lọt hoàn toàn** sự cố của challenge, dù người dùng phải chờ
gấp 17 lần bình thường. Nguyên nhân: ngưỡng 3000 ms được đặt cao hơn `latency_threshold_ms = 2000`
mà `config/challenge.json` quy định.

**Đề xuất:** hạ `latency_p95_ms` objective từ 3000 xuống **2000 ms** cho khớp ngưỡng của
challenge, và sửa điều kiện `HighLatencyP95` thành `latency_p95_ms > 2000 for 5m`. Nhóm ghi
nhận đây là khoảng trống chưa sửa tại thời điểm nộp, không phải là thiết kế có chủ đích.

## 6. Điều tra challenge

Chi tiết đầy đủ: [`evidence/challenge_investigation.md`](evidence/challenge_investigation.md).

- Challenge ID: `day13-k4-observability-v1` (cohort K4, incident `rag_slow`,
  `affected_feature = monitoring`, `latency_threshold_ms = 2000`, seed 1304).
- Triệu chứng từ metrics: **thuần tuý latency, không có lỗi.** So sánh 5 request trước và
  5 request sau khi bật incident, cùng bộ input của challenge:

  | Chỉ số | Trước | Sau | |
  |---|---|---|---|
  | latency p50 | 152 ms | **2652 ms** | ×17.4 |
  | latency p95 | 1099 ms | **2682 ms** | vượt ngưỡng 2000 ms |
  | error_rate_pct | 0% | **0%** | không đổi |
  | quality_score avg | 0.840 | 0.840 | không đổi |

  Điểm mấu chốt: `error_rate_pct` giữ nguyên 0%. Nếu chỉ theo dõi error rate thì sự cố này
  vô hình.

- Trace ID liên quan: `7a12658006ca57379d4fe4bff6176823` (có incident) so với
  `8bdf023e34a6eaaaa3a3b65e9963fd99` (khoẻ mạnh). Span `rag.retrieve` = **2500/2652 ms (94%)**
  khi có incident, và **0 ms** khi khoẻ mạnh; span `llm.generate` giữ nguyên 151 ms ở cả hai —
  loại trừ LLM khỏi diện nghi vấn.
- Log line/correlation ID liên quan: `req-07aec384` (`session_id = k4-challenge-s01`,
  `feature = monitoring`, `user_id_hash = f00ba60b3772`). Log ghi `latency_ms = 2651`, khớp với
  span `run` trong trace, và có `response_sent` chứ không có `request_failed` — xác nhận request
  **thành công nhưng chậm**.
- Root cause: `app/mock_rag.py:19-20` — `if STATE["rag_slow"]: time.sleep(2.5)`. Vector store
  retrieval bị chèn độ trễ cố định 2.5 giây. Toàn bộ phần tăng thêm của latency đến từ đây,
  không phải từ LLM, mạng hay tăng tải.
- Fix action: tắt incident bằng `python scripts/inject_incident.py --disable` (đã xác nhận
  `{'rag_slow': False}`, p50 trở lại ~152 ms). Với sự cố thật tương đương: đặt timeout cho
  `retrieve()` và trả fallback answer thay vì để request treo, kèm circuit breaker cho vector store.
- Preventive measure:
  1. **Alert theo latency, không chỉ theo error rate** — xem khoảng trống đã phân tích ở mục 5.
  2. **Không gọi code chặn trong endpoint `async`.** `/chat` khai báo `async def` nhưng gọi
     `agent.run()` đồng bộ có `time.sleep`, làm nghẽn cả event loop. Chạy `--concurrency 5`,
     client đo được **10.6–13.3 s** trong khi app chỉ ghi `latency_ms = 2651 ms` — 5 request bị
     xếp hàng tuần tự. Nên chuyển `/chat` sang `def` thường để FastAPI tự đẩy sang threadpool.
  3. **Giám sát chênh lệch giữa `x-response-time-ms` (middleware đo, gồm cả thời gian chờ) và
     `latency_ms` (đo bên trong handler).** Khoảng cách giãn ra là dấu hiệu sớm của nghẽn hàng đợi.
  4. **Giữ trace riêng cho từng sub-component.** Không có span `rag.retrieve` tách biệt thì trace
     chỉ hiện `run = 2652 ms` và điều tra sẽ phải đoán.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| A — Trịnh Bá Khánh Trình | CP1 Middleware: gán/propagate Correlation ID, enrich log context (`user_id_hash`, `session_id`, `feature`, `model`, `env`), exception handler cho 422/500 | [PR #4](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/4) (`f0d28e0`), [PR #5](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/5) (`91cf51b`), [PR #1](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/1) (`9e7f153`) | Context phải bind **trước** `call_next` thì log sau mới thừa hưởng; `clear_contextvars()` là bắt buộc vì worker tái sử dụng context giữa các request. Handler của `Exception` nằm ngoài middleware (gắn vào `ServerErrorMiddleware`) nên phải tự set header `x-request-id`, nếu không response lỗi sẽ không truy vết được — đúng lúc cần nhất. Bài học thứ hai: enrichment từng bị mất khi merge nhánh khác (`c6aa5e8`) mà không ai phát hiện, chỉ có test tự viết bắt được — nên test là thứ bảo vệ phần việc của mình. |
| B — Nguyễn Hoàng Đạt (2A202601460) | CP1 PII Scrubbing: thêm regex patterns (passport, địa chỉ VN), bật processor `scrub_event` trong chain logging, kiểm chứng log không lộ PII | [PR #2](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/2) (`bc86eb3`) | _(tự điền)_ |
| C — Nguyễn Hữu Tuyến (2A202601520) | Triển khai `error_rate_pct` theo tổng số request, thiết kế dashboard 6 nhóm chỉ số (latency, traffic, errors, cost, tokens, quality), viết test và validator | `8bd03d2` — commit đẩy thẳng lên `main`, chưa qua PR | _(tự điền)_ |
| D — Nguyễn Văn Phúc (2A202601350) | CP2: thiết lập SLO, viết Alert rules và Alert Runbook xử lý sự cố | [PR #3](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/3) (`7e75441`) | _(tự điền)_ |
| E — Vũ Thành Khang (2A202601866) | Chạy load test, bọc trace cho sub-component RAG/LLM (phần mở rộng), dẫn dắt điều tra Challenge (CP3), hoàn thiện báo cáo nhóm | [PR #6](https://github.com/khanhtrinh2/Day13-K4-Observability/pull/6) (`e6c7b7c`, `c6aa5e8`) | _(tự điền)_ |
