# Yêu cầu dashboard

Contract có thể kiểm tra bằng máy nằm tại `config/dashboard.yaml`. Hướng dẫn dựng và kiểm tra runtime nằm tại [DASHBOARD_SETUP.md](DASHBOARD_SETUP.md).

Dashboard chính cần đủ 6 nhóm thông tin:

1. Latency P50/P95/P99.
2. Traffic: request count hoặc QPS.
3. Error rate và breakdown theo loại lỗi.
4. Cost theo thời gian.
5. Tổng token input/output.
6. Quality proxy.

## Đặc tả 6 panel

| Panel ID | Chỉ số hiển thị | Nguồn dữ liệu | Phép tính | Ngưỡng |
|---|---|---|---|---|
| `latency` | P50, P95, P99 | `response_sent.latency_ms` | percentile trên cửa sổ đang chọn | P95 <= 3.000 ms |
| `traffic` | Request/phút | `request_received` | đếm theo bucket 1 phút | >= 1 request/phút |
| `errors` | Tỷ lệ lỗi và breakdown | `request_received`, `request_failed.error_type` | `request_failed / request_received * 100`; đếm theo `error_type` | <= 2% |
| `cost` | Chi phí theo phút và tổng | `response_sent.cost_usd` | tổng theo bucket 1 phút và toàn cửa sổ | <= 2,5 USD |
| `tokens` | Tổng input/output token | `response_sent.tokens_in`, `tokens_out` | tổng riêng từng field | <= 50.000 token |
| `quality` | Quality trung bình | `response_sent.quality_score` | mean | >= 0,75 |

Với panel `errors`, mẫu số là tất cả event `request_received`, kể cả
request sau đó thành công hoặc thất bại. Nếu cửa sổ không có request thì
hiển thị `0%` thay vì chia cho 0. Endpoint `/metrics` dùng cùng semantics,
nhưng tính từ `successful requests + errors` vì hai loại được ghi ở hai
counter runtime khác nhau.

## Bố cục đề xuất

- Hàng 1: `latency`, `traffic`, `errors` để nhìn nhanh tình trạng dịch vụ.
- Hàng 2: `cost`, `tokens`, `quality` để theo dõi hiệu quả AI.
- Time range mặc định 60 phút, refresh 30 giây; mỗi panel hiện đơn vị
  và đường threshold theo `config/dashboard.yaml`.

Tiêu chuẩn trình bày:

- Khoảng thời gian mặc định: 1 giờ.
- Tự refresh mỗi 15–30 giây nếu công cụ hỗ trợ.
- Có threshold hoặc SLO line.
- Ghi rõ đơn vị.
- Chỉ giữ 6–8 panel quan trọng ở lớp chính.
- Screenshot phải nhìn được tên panel và khoảng thời gian.

Kiểm tra contract trước khi chụp evidence:

```bash
python scripts/validate_dashboard.py
```
