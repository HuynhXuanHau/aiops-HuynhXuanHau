# W3-D2 Submission — Huỳnh Xuân Hậu

## 3 thứ tôi học được về AIOps pipeline của mình
1. **Phát hiện lỗi (Detect) là dễ, tìm đúng bệnh (RCA) mới khó:** Bảng điểm 10/10 Detected cho thấy giám sát hoạt động tốt, nhưng RCA 4/10 chứng minh rằng nếu không có đồ thị Topology, AI chỉ đang "đoán mò".
2. **Thiên kiến của thuật toán (RCA Bias):** Pipeline rất dễ bị lừa bởi "loudest service" (service la hét to nhất). Nếu Payment sinh ra quá nhiều log lỗi, AI sẽ mặc định nó là thủ phạm dù gốc rễ nằm ở DNS hay Gateway.
3. **Giá trị của Chaos Engineering:** Chạy 10 bài test tự động giúp phơi bày ngay lập tức điểm yếu cốt lõi của Correlator mà Unit test hay Load test thông thường không thể nào thấy được.

## 1 fault mà tôi mong pipeline catch nhưng nó miss
- **Experiment:** `9_dns_slowdown`
- **Why I expected detection & correct RCA:** DNS chậm sẽ ảnh hưởng đến mọi HTTP call, tôi kỳ vọng đồ thị RCA sẽ chỉ ra được gốc rễ từ tầng Network.
- **Why pipeline missed (hypothesis):** Pipeline đã bắt được lỗi (Detected: Y) nhưng lại bắt nhầm thủ phạm là `payment-svc`. Lý do là AIOps hiện tại chỉ gom cụm dựa trên mốc thời gian (temporal cluster) mà không tra cứu theo chiều sâu (dependency graph).

## 1 trade-off trong design pipeline mà tôi muốn rethink
**Trade-off giữa Thời gian bắt lỗi (MTTD) và Độ chính xác (Accuracy):**
Hiện tại, pipeline mất trung bình 96 giây để phát hiện lỗi. Nếu tôi giảm cửa sổ thời gian xuống để bắt lỗi trong 10 giây, nguy cơ bắt nhầm (False Positives/Noise) sẽ tăng vọt. Sự đánh đổi này là không đáng, tôi sẽ chọn giữ MTTD ở mốc ~1 phút nhưng đầu tư mạnh hơn vào thuật toán nâng cấp RCA.

## Scoreboard summary
- **detected:** 10/10
- **rca_correct:** 4/10
- **mttd_p50:** 96s
- **false_alarms:** 0
- **verdict:** FAILED RCA ACCEPTANCE 