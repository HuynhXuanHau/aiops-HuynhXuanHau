# Chaos Engineering Report — [Điền tên bạn vào đây]

## 1. Setup
- **Stack version:** v1.0 (Local Docker Compose - 10 mock microservices)
- **Pipeline version:** FastAPI AIOps v1.0 (Mock Pipeline)
- **Baseline window:** 2026-06-17T07:50:00Z → 2026-06-17T07:55:00Z (300s)
- **Total experiments run:** 10

## 2. Results table
- Total: 10
- Detected: 10/10
- RCA correct: 4/10
- False alarms in baseline windows: 0
- Precision: 1.00
- Recall: 1.00
- MTTD p50: 96s, p95: 160s

Per-experiment:
| #  | name                      | detected | mttd   | rca_service     | rca_correct |
|---|---------------------------|----------|--------|-----------------|-------------|
| 1  | 1_payment_latency         | Y        | 94s    | payment-svc     | Y           |
| 2  | 2_payment_loss            | Y        | 94s    | payment-svc     | Y           |
| 3  | 3_inventory_kill          | Y        | 93s    | payment-svc     | N           |
| 4  | 4_gateway_cpu             | Y        | 160s   | payment-svc     | N           |
| 5  | 5_payment_db_memory       | Y        | 94s    | payment-svc     | Y           |
| 6  | 6_auth_clock_skew         | Y        | 156s   | payment-svc     | N           |
| 7  | 7_log_disk_fill           | Y        | 160s   | payment-svc     | N           |
| 8  | 8_frontend_gateway_partit | Y        | 96s    | payment-svc     | N           |
| 9  | 9_dns_slowdown            | Y        | 159s   | payment-svc     | N           |
| 10 | 10_checkout_retry_storm   | Y        | 94s    | payment-svc     | Y           |

## 3. Detailed per-experiment analysis
*(Phân tích đại diện cho các cụm kết quả)*

- **Các bài test 1, 2, 5, 10 (Lỗi tại payment-svc):** - **Observed:** Detected = Y, RCA = Y. Hệ thống phát hiện lỗi sau ~94s và trỏ chính xác về `payment-svc`.
  - **Match expected?:** Có. Bộ não AI hoạt động hiệu quả khi lỗi nằm ở service trung tâm.

- **Các bài test 3, 4, 6, 7, 8, 9 (Lỗi tại các service khác):**
  - **Observed:** Detected = Y, nhưng RCA = N (Tất cả đều trỏ nhầm về `payment-svc`). 
  - **Match expected?:** Không. Dù hệ thống có bắt được tín hiệu bất thường, nhưng module phân tích nguyên nhân gốc rễ (RCA) đã chẩn đoán sai hoàn toàn.

## 4. Gap analysis — top 3 pipeline weakness

1. **Symptom:** RCA Correct chỉ đạt 4/10 (40%), trượt tiêu chuẩn Acceptance (≥ 70%). Trong 6 bài test lỗi ở các service khác nhau, RCA luôn đổ lỗi cho `payment-svc`.
   - **Likely cause in pipeline:** *Tham chiếu §7.3 - RCA wrong root*. Thuật toán RCA của Pipeline hiện tại đang bị "hardcode" hoặc có thiên kiến (bias) quá mức đối với service có volume giao dịch lớn nhất (`payment-svc`), khiến nó luôn pick service ồn ào nhất thay vì truy vết trên đồ thị.
   - **Recommended fix:** Cập nhật thuật toán Correlator thành Topology-aware (nhận thức được sơ đồ mạng). Bắt buộc phải áp dụng thuật toán Granger causality để theo dõi độ trễ thời gian (lag) giữa các service.

2. **Symptom:** MTTD (Mean Time To Detect) khá cao: p50 là 96s, p95 lên tới 160s.
   - **Likely cause in pipeline:** Các luật cảnh báo (Alert Rules) đang sử dụng hàm trung bình trượt với khung thời gian (window) quá rộng, hoặc quá trình Correlator gom cụm đang chờ quá lâu để tránh báo động giả (False Alarms).
   - **Recommended fix:** Áp dụng mô hình Multi-Window Multi-Burn-Rate (MWMBR) với các cửa sổ ngắn (vd: 5 phút) để rút ngắn MTTD xuống dưới 60s cho các sự cố Critical.

3. **Symptom:** Tool Pumba không tìm thấy `payment-svc` và `inventory-svc` trong lúc tiêm lỗi (báo lỗi `no containers found`).
   - **Likely cause in pipeline:** Vấn đề nằm ở tính ổn định của hạ tầng (Target Stack). Các container này có thể đã rơi vào trạng thái CrashLoopBackOff trước cả khi bài test bắt đầu do lỗi timeout nội bộ.
   - **Recommended fix:** Thêm Liveness/Readiness probes vào Docker Compose để đảm bảo các container thực sự "sống" trước khi chaos runner kích hoạt.