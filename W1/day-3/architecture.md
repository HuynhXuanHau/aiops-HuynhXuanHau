# End-to-End Data Layer Architecture
**Use Case:** Anomaly Detection trên Payment Service (Phát hiện bất thường trong giao dịch/độ trễ hệ thống thanh toán)

## 1. Sơ đồ luồng dữ liệu (Data Flow)
![alt text](architecture.png)
[Service] -> [Collection] -> [Transport] -> [Processing] -> [Storage] -> [Query/ML]

## 2. Chi tiết các thành phần (Component Stack)

**1. Service Layer:**
* **Mô tả:** Các microservices chạy hệ thống thanh toán (VD: `checkout-service`, `payment-gateway`).
* **Hành động:** Phát sinh các metric quan trọng (ví dụ: `payment_latency_ms`, `transaction_success_rate`, `cpu_usage`).

**2. Collection Layer: OpenTelemetry (OTel) Collector**
* **Lý do chọn:** Chuẩn chung của CNCF (vendor-neutral), không bị phụ thuộc vào một nhà cung cấp cụ thể. OTel agent chạy dưới dạng sidecar/daemonset trong Kubernetes để thu thập toàn bộ metrics/traces từ các service.

**3. Transport Layer: Apache Kafka**
* **Lý do chọn:** Đóng vai trò là Message Queue/Buffer. Thanh toán là dịch vụ quan trọng, lúc cao điểm (flash sale) lượng metrics bắn ra khổng lồ. Kafka giúp hệ thống lưu trữ phía sau không bị quá tải (backpressure) và không bị mất dữ liệu.

**4. Processing Layer: Apache Flink (Streaming Engine)**
* **Lý do chọn:** Flink sẽ đọc trực tiếp luồng dữ liệu từ Kafka để tính toán các Features theo thời gian thực (Giống như cách script `pipeline.py` tính `rolling_mean` và `rate_of_change` on-the-fly). Xử lý ngay lập tức độ trễ (latency) < 1 giây.

**5. Storage Layer:**
* **Hot Storage (Dữ liệu mới, truy vấn nhanh):** `VictoriaMetrics` (TSDB - Cơ sở dữ liệu chuỗi thời gian). Tương thích với Prometheus nhưng scale tốt hơn, nén dữ liệu tốt hơn. Giữ data nóng trong vòng 30 ngày.
* **Cold Storage (Dữ liệu lịch sử):** Đẩy dữ liệu cũ (đã tính features) về `AWS S3` (dưới dạng Parquet) để tiết kiệm chi phí lưu trữ dài hạn.

**6. Query/ML Layer:**
* **Feature Store:** Đẩy các features streaming từ Flink vào `Redis` (Online store) để ML Model gọi ra infer với độ trễ cực thấp (< 50ms).
* **ML Pipeline:** Model Anomaly Detection liên tục lấy data từ Redis, nếu dự đoán (predict) ra bất thường -> Kích hoạt Alerting (PagerDuty/Slack).
* **Dashboard:** Dùng `Grafana` kết nối vào VictoriaMetrics để đội SRE theo dõi chart realtime.