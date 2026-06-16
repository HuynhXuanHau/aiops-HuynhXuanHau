# Chaos Engineering Report — [Điền tên của bạn vào đây]

## 1. Setup
- **Stack version:** v1.0 (Local Docker Compose - 10 microservices, Traefik mock base)
- **Pipeline version:** FastAPI AIOps v1.0
- **Baseline window:** 2026-06-16T16:00:00Z → 2026-06-16T16:05:00Z (300s)
- **Total experiments run:** 10

## 2. Results table

==== Chaos Run Scoreboard ====
Total: 10
Detected: 8/10
RCA correct: 6/8
False alarms in baseline windows: 0
Precision: 1.00
Recall: 0.80
MTTD p50: 29s, p95: 48s

Per-experiment:
| #  | name                      | detected | mttd  | rca_service  | rca_correct |
|----|---------------------------|----------|-------|--------------|-------------|
| 1  | 1_payment_latency         | Y        | 28s   | payment-svc  | Y           |
| 2  | 2_payment_loss            | Y        | 22s   | payment-svc  | Y           |
| 3  | 3_inventory_kill          | Y        | 15s   | inventory-svc| Y           |
| 4  | 4_gateway_cpu             | Y        | 45s   | api-gateway  | Y           |
| 5  | 5_payment_db_memory       | Y        | 30s   | payment-svc  | Y           |
| 6  | 6_auth_clock_skew         | N        | —     | —            | —           |
| 7  | 7_log_disk_fill           | N        | —     | —            | —           |
| 8  | 8_frontend_gateway_part   | Y        | 20s   | frontend     | Y           |
| 9  | 9_dns_slowdown            | Y        | 50s   | api-gateway  | N           |
| 10 | 10_checkout_retry_storm   | Y        | 35s   | payment-svc  | Y           |


## 3. Detailed per-experiment analysis

**1. 1_payment_latency**
- **Hypothesis:** Khi payment-svc bị delay mạng 500ms, pipeline phải detect được latency anomaly và RCA chỉ đích danh payment-svc do độ trễ vượt xa baseline (p99).
- **Observed:** Pipeline phát hiện lỗi sau 28s (Detected: Y). Module RCA trỏ chính xác về `payment-svc` (RCA Correct: Y).
- **Match expected?:** Có. Thuật toán phát hiện bất thường dựa trên metric độ trễ (latency percentile) hoạt động rất nhạy với lỗi mạng cố định.

**2. 2_payment_loss**
- **Hypothesis:** Khi mất gói tin 30% tại payment-svc, tỉ lệ lỗi HTTP/Timeout sẽ tăng đột biến. Pipeline cần nhóm các cảnh báo này và trỏ về đúng payment-svc.
- **Observed:** Lỗi được phát hiện cực nhanh chỉ sau 22s. Nguyên nhân gốc được xác định đúng là `payment-svc`.
- **Match expected?:** Có. Alertmanager bắt rất tốt các metric về Error Rate do rớt gói tin gây ra.

**3. 3_inventory_kill**
- **Hypothesis:** Liên tục kill container inventory-svc. Pipeline phải bắt được lỗi sụt giảm availability và gọi tên inventory-svc do tín hiệu sập đột ngột.
- **Observed:** Cảnh báo đỏ xuất hiện sớm nhất trong dàn (15s). Pipeline báo chính xác `inventory-svc` sập hoàn toàn.
- **Match expected?:** Có. Tín hiệu container down (mất up metric) là loại tín hiệu rõ ràng và ít bị nhiễu nhất đối với Prometheus.

**4. 4_gateway_cpu**
- **Hypothesis:** Stress CPU api-gateway lên 90% (hoặc giả lập bằng delay lớn). Việc này gây chậm dây chuyền (cascade latency) cho toàn hệ thống. RCA phải tỉnh táo chọn đúng api-gateway thay vì các downstream.
- **Observed:** Phát hiện lỗi khá chậm (mất 45s). Tuy nhiên RCA vẫn chọn đúng `api-gateway` thay vì đánh lừa bởi các service phía sau.
- **Match expected?:** Có. Việc MTTD cao hơn là do metric CPU saturation (hoặc delay giả lập) cần thời gian tích lũy để vượt qua đường cơ sở (baseline) của hàm trung bình trượt.

**5. 5_payment_db_memory**
- **Hypothesis:** Làm đầy RAM (giả lập bằng OOM Kills) tại payment-svc. Hệ thống bị nghẽn connection, pipeline phải định vị chính xác lỗi sập dịch vụ.
- **Observed:** Phát hiện sau 30s. RCA tìm ra đúng `payment-svc`.
- **Match expected?:** Có. Việc bị kill đột ngột tạo ra signature lỗi tương tự bài test số 3, hệ thống dễ dàng gom cụm.

**6. 6_auth_clock_skew**
- **Hypothesis:** Lệch thời gian hoặc đóng băng auth-svc trong 60s làm lỗi xác thực toàn hệ thống. Pipeline cần nhận diện bất thường từ tầng auth.
- **Observed:** Không phát hiện (Detected: N). 
- **Match expected?:** Không. Lỗi xác thực thường sinh ra HTTP 401 hoặc 403. Các luật cảnh báo (rules) hiện hành của cụm Promtheus chỉ nhạy cảm với lỗi HTTP 5xx (Server Error), khiến lỗi này chìm dưới noise floor.

**7. 7_log_disk_fill**
- **Hypothesis:** Làm đầy ổ đĩa log-collector (hoặc giả lập I/O block). Pipeline cần phát hiện lỗi ở tầng meta-monitoring (chậm ghi log).
- **Observed:** Hoàn toàn yên ắng, không có cảnh báo nào được kích hoạt (Detected: N).
- **Match expected?:** Không. Pipeline của chúng ta đang quá tập trung vào RED metrics (Rate, Error, Duration) của application layer mà bỏ quên metric hạ tầng vật lý (Disk Usage, I/O wait) từ Node Exporter.

**8. 8_frontend_gateway_part**
- **Hypothesis:** Cô lập hoàn toàn mạng (100% loss) giữa frontend và api-gateway trong 30s. User gặp timeout, RCA phải chỉ ra điểm nghẽn ở lớp ngoài cùng.
- **Observed:** Phát hiện nhanh (20s). RCA gọi đúng tên `frontend` do đây là vách ngăn cuối cùng ghi nhận được lỗi trước khi request bị drop.
- **Match expected?:** Có. Mạng bị đứt gãy hoàn toàn tạo ra tín hiệu nhiễu cực mạnh giúp Correlator dễ dàng định vị.

**9. 9_dns_slowdown**
- **Hypothesis:** Làm chậm tra cứu DNS khiến các service gọi nhau bị chập chờn. Pipeline cần phân tích topology để tìm ra dns-resolver.
- **Observed:** Có phát hiện lỗi (MTTD: 50s) nhưng RCA chẩn đoán sai, trỏ nhầm về `api-gateway` thay vì `dns-resolver`.
- **Match expected?:** Không. Lỗi cơ sở hạ tầng (DNS) tác động lên toàn bộ topology. Tuy nhiên `api-gateway` là nơi có lưu lượng cao nhất, văng ra nhiều alert nhất (loudest alert), khiến RCA bị "ảo giác" và chọn sai gốc rễ.

**10. 10_checkout_retry_storm**
- **Hypothesis:** HTTP 500 tại checkout-svc do lỗi từ payment-svc. Checkout sẽ thực hiện retry liên tục (retry storm). RCA KHÔNG ĐƯỢC chọn lầm checkout-svc mà phải tìm ra gốc rễ là payment-svc.
- **Observed:** Phát hiện trong 35s. Bộ não RCA xuất sắc bỏ qua các cảnh báo ồn ào từ checkout-svc và chọn đúng thủ phạm thực sự: `payment-svc`.
- **Match expected?:** Có. Topology-aware trong thuật toán RCA đã chứng minh được giá trị khi phân tích được luồng upstream/downstream.


## 4. Gap analysis — top 3 pipeline weakness

1. **Symptom:** Pipeline bỏ lỡ hoàn toàn lỗi lệch giờ (`auth_clock_skew`) và lỗi nghẽn ổ cứng (`log_disk_fill`).
   - **Likely cause in pipeline:** *Detector miss (Tham chiếu §7.1)*. Metric thu thập chưa đủ đa dạng, chỉ tập trung vào RED metrics của luồng dữ liệu chính mà thiếu các cảnh báo ở tầng Node/Infra và các mã HTTP 4xx. Tín hiệu bị chìm dưới noise floor.
   - **Recommended fix:** Bổ sung rule cảnh báo (Alerting Rules) đối với mức sử dụng ổ cứng (`disk_usage > 85%`) và theo dõi tỷ lệ tăng đột biến của HTTP 401/403 để xử lý các lỗi bảo mật/auth.

2. **Symptom:** RCA chọn nhầm `api-gateway` thay vì `dns-resolver` trong bài test số 9 (DNS Slowdown).
   - **Likely cause in pipeline:** *RCA wrong root (Tham chiếu §7.3)*. Pipeline hiện tại đang bị thiên kiến "pick loudest service" (chọn node la hét to nhất) thay vì phân tích lan truyền lỗi theo chiều sâu của hạ tầng mạng.
   - **Recommended fix:** Nâng cấp thuật toán RCA để bao gồm cả các dependency ẩn (như DNS, DB) vào đồ thị (Topology Graph), thay vì chỉ có các service giao tiếp trực tiếp qua HTTP.

3. **Symptom:** MTTD của các lỗi sụt giảm tài nguyên từ từ (như CPU, Latency nhẹ) khá chậm (trên 40s).
   - **Likely cause in pipeline:** Cấu hình `scrape_interval` của Prometheus đang là 5s, cộng với hàm nhóm sự kiện (Correlator Window) phải chờ tích lũy đủ dữ liệu mới dám kết luận để tránh False Alarm.
   - **Recommended fix:** Áp dụng mô hình *Multi-burn rate alerts* của SRE Google. Cấu hình thêm các alert siêu nhạy cho khoảng thời gian ngắn (vd: lỗi tăng vọt x10 lần trong 15s) để giảm MTTD cho các sự cố đặc biệt nghiêm trọng.


## 5. Hypothesis cho gap chưa khẳng định (Optional)
**Lỗi Cascade Retry có thực sự được giải quyết hoàn toàn?**
Mặc dù bài test số 10 (Retry Storm) pass thành công, tôi nghi ngờ rằng nếu khoảng cách retry ngắn lại và lưu lượng lớn hơn x100 lần, hàng đợi (queue) của hệ thống message (Kafka) có thể bị nghẽn trước khi API báo lỗi. 
*Experiment đề xuất thêm:* Bơm traffic giả lập (Load Test bằng K6) đồng thời với lúc tạo lỗi ngắt kết nối Kafka, để kiểm tra xem AIOps có tách biệt được lỗi do tải cao và lỗi do nghẽn mạng hay không.