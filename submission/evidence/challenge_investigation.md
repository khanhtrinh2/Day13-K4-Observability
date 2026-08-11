# CP3 — Điều tra challenge `day13-k4-observability-v1`

Ngày 2026-08-11. Cohort K4. Incident đọc từ `config/challenge.json`, không tự chọn.

```
challenge_id          : day13-k4-observability-v1
incident              : rag_slow
affected_feature      : monitoring
latency_threshold_ms  : 2000
seed                  : 1304
```

Cách chạy:

```bash
python scripts/load_test.py --challenge              # pha healthy, chưa bật incident
python scripts/inject_incident.py                    # bật rag_slow theo challenge.json
python scripts/load_test.py --challenge --concurrency 5
```

---

## Tầng 1 — METRICS: phát hiện triệu chứng

Percentile tính từ `data/logs.jsonl` bằng chính `app.metrics.percentile`, tách hai pha
theo mốc log `incident_enabled` lúc `2026-08-11T10:04:20.753317Z`.

| Chỉ số | Trước incident (5 req) | Sau incident (5 req) | |
|---|---|---|---|
| latency p50 | 152 ms | **2652 ms** | ×17.4 |
| latency p95 | 1099 ms | **2682 ms** | vượt SLO 2000 ms |
| latency p99 | 1099 ms | 2682 ms | |
| error_rate_pct | 0% | **0%** | không có lỗi nào |
| quality_score avg | 0.840 | 0.840 | không đổi |
| tokens / cost | bình thường | bình thường | không đổi |

**Triệu chứng:** thuần tuý là sự cố **latency**, không phải sự cố lỗi. `error_rate_pct`
giữ nguyên 0%, chất lượng và chi phí không đổi — nếu chỉ cảnh báo theo error rate thì
sự cố này sẽ **không bao giờ được phát hiện**. Đây là lý do SLO phải có ngưỡng latency
riêng.

Metrics chỉ cho biết *"chậm ở đâu đó"*, chưa cho biết *chậm ở đâu*.

---

## Tầng 2 — TRACES: khoanh vùng span bất thường

Hai trace cùng `session_id = k4-challenge-s01`, cùng một câu hỏi, khác nhau ở chỗ có
bật incident hay không:

**Trace khi có incident — `7a12658006ca57379d4fe4bff6176823`**

```
span                    start(+ms)   duration(ms)
run                              0           2652   ##########################
rag.retrieve                     0           2500   #########################
llm.generate                  2500            151   #
```

**Trace lúc khoẻ mạnh — `8bdf023e34a6eaaaa3a3b65e9963fd99`**

```
span                    start(+ms)   duration(ms)
run                              0            154   #
rag.retrieve                     1              0
llm.generate                     3            151   #
```

**Kết luận từ trace:** `rag.retrieve` chiếm **2500/2652 ms = 94%** tổng thời gian.
`llm.generate` giữ nguyên 151 ms ở cả hai pha — LLM hoàn toàn vô can. Vấn đề nằm ở
tầng retrieval.

---

## Tầng 3 — LOGS: chứng minh root cause

Truy theo `correlation_id = req-07aec384`:

```json
{"service": "api", "event": "request_received", "correlation_id": "req-07aec384",
 "feature": "monitoring", "session_id": "k4-challenge-s01", "user_id_hash": "f00ba60b3772",
 "model": "claude-sonnet-4-5", "env": "dev",
 "payload": {"message_preview": "Explain why metrics traces and logs work together."},
 "ts": "2026-08-11T10:04:42.106429Z"}

{"service": "api", "event": "response_sent", "correlation_id": "req-07aec384",
 "latency_ms": 2651, "tokens_in": 35, "tokens_out": 136, "cost_usd": 0.002145,
 "quality_score": 0.8, "feature": "monitoring", "session_id": "k4-challenge-s01",
 "ts": "2026-08-11T10:04:44.759422Z"}
```

Log xác nhận request thành công (`response_sent`, không có `request_failed`), đúng
`feature=monitoring` như `affected_feature` trong challenge, và `latency_ms=2651` khớp
với span `run` trong trace.

**Root cause:** `app/mock_rag.py:19-20`

```python
if STATE["rag_slow"]:
    time.sleep(2.5)
```

Vector store retrieval bị chèn độ trễ cố định 2.5 giây. Toàn bộ độ trễ tăng thêm đến
từ đây, không phải từ LLM, không phải từ mạng, không phải từ tăng tải.

---

## Phát hiện thêm: độ trễ người dùng thực tế lớn hơn số app tự ghi

Khi chạy `--concurrency 5`, client đo được **10.6–13.3 giây**, trong khi app ghi
`latency_ms = 2651 ms`. Chênh lệch ~5 lần.

Nguyên nhân: `/chat` khai báo `async def` (`app/main.py:47`) nhưng bên trong gọi
`agent.run()` là code đồng bộ có `time.sleep()`. `time.sleep` **chặn cả event loop**,
nên 5 request đồng thời bị xếp hàng tuần tự thay vì chạy song song:
5 × 2.65 s ≈ 13.3 s.

`latency_ms` chỉ đo từ lúc `agent.run` bắt đầu, nên **không bao gồm thời gian chờ hàng đợi**.
Bài học: chỉ đo latency bên trong handler sẽ che giấu nỗi đau thật của người dùng khi hệ
thống bị nghẽn. Cần đo thêm ở tầng ngoài — header `x-response-time-ms` do middleware gắn
chính là số đo bao gồm cả thời gian chờ này.

---

## Fix action

1. **Ngay lập tức:** tắt incident — `python scripts/inject_incident.py --disable`.
   Đã xác nhận: `{'rag_slow': False}`, p50 trở lại ~152 ms.
2. **Với sự cố thật tương đương:** đặt timeout cho `retrieve()` (ví dụ 500 ms) và trả
   fallback answer thay vì để request treo; thêm circuit breaker cho vector store.

## Preventive measure

1. **Alert theo latency, không chỉ theo error rate.** Sự cố này giữ `error_rate_pct = 0%`
   suốt thời gian xảy ra. Nếu chỉ có alert error thì không ai biết. Cần alert
   `latency_p95 > 2000 ms` duy trì vài phút (khớp `latency_threshold_ms` trong challenge).
2. **Không gọi code chặn trong endpoint `async`.** Chuyển `/chat` sang `def` thường để
   FastAPI tự đẩy sang threadpool, hoặc bọc `agent.run` bằng `run_in_threadpool`. Nếu
   không, một sub-component chậm sẽ kéo sập throughput của toàn bộ API.
3. **Giám sát chênh lệch giữa `x-response-time-ms` và `latency_ms`.** Khoảng cách giãn ra
   là dấu hiệu sớm của nghẽn hàng đợi, xuất hiện trước khi người dùng kịp phàn nàn.
4. **Bọc trace cho từng sub-component.** Nếu `rag.retrieve` và `llm.generate` không được
   tách span riêng, trace chỉ hiện `run = 2652 ms` và việc điều tra sẽ phải đoán mò.
