# W3-D2 Submission — Huỳnh Xuân Hậu

## 3 thứ tôi học được về AIOps pipeline của mình
1. **Sự nhiễu loạn của Topology:** Các lỗi ở tầng mạng chung (như DNS) rất dễ khiến AIOps bị đánh lừa và đổ tội cho Gateway, vì Gateway là nơi hứng chịu và ghi nhận hậu quả nặng nề nhất.
2. **Tầm quan trọng của External Probe:** Theo dõi hệ thống bằng nội bộ (Prometheus) là chưa đủ. Có những lúc metric nội bộ vẫn báo xanh nhưng user thực tế (Probe) đã bị timeout do nghẽn cổ chai ở luồng ngoài.
3. **Giá trị của Cooldown:** Nếu không có thời gian nghỉ (120s) giữa các bài test, các alert sẽ bị dính chùm vào nhau tạo thành một cụm (cluster) khổng lồ, khiến mọi thuật toán RCA đều sụp đổ.

## 1 fault mà tôi mong pipeline catch nhưng nó miss
- **Experiment:** `6_auth_clock_skew` (Lệch giờ hệ thống).
- **Why I expected detection:** Lệch giờ sẽ phá hỏng toàn bộ các phiên xác thực JWT, tôi đinh ninh hệ thống sẽ sụp đổ và báo động đỏ ngay lập tức.
- **Why pipeline missed (hypothesis):** Việc từ chối JWT sinh ra lỗi 401 (Unauthorized). Tuy nhiên, bộ luật (rules) của Prometheus hiện tại chỉ được cài đặt để kích hoạt cảnh báo (firing) khi lỗi 5xx tăng vọt, do đó lỗi 4xx bị coi là "hành vi bình thường của user" và bị bỏ qua hoàn toàn.

## 1 trade-off trong design pipeline mà tôi muốn rethink
**Trade-off giữa Thời gian phát hiện (MTTD) và Cảnh báo giả (False Alarms):**
Hiện tại, pipeline yêu cầu một bất thường phải duy trì liên tục trong 30-60 giây thì mới nhóm thành sự cố để tránh bị nhiễu do mạng chập chờn. Việc này giúp False Alarm = 0, nhưng lại đánh đổi bằng MTTD khá chậm. Sắp tới tôi muốn áp dụng Multi-burn rate (cảnh báo theo nhiều ngưỡng thời gian khác nhau) để vừa phát hiện nhanh lỗi lớn, vừa không bị báo động giả với lỗi nhỏ.

## Scoreboard summary
- **detected:** 8/10
- **rca_correct:** 6/8
- **mttd_p50:** 25s
- **false_alarms:** 0
- **verdict:** ĐẠT (Passed Acceptance Checklist)