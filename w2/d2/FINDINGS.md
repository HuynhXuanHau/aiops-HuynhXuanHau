# W2-D2 Findings: Graph & Retrieval RCA

**1. Phân tích Cluster chính (`c-000-000`)**
Trong cluster lớn nhất, thuật toán đã xác định chính xác `payment-svc` là nguyên nhân gốc rễ, phân loại đúng lỗi thuộc nhóm `connection_pool_exhaustion`. Lý do `payment-svc` được chọn là vì nó đứng ở vị trí cuối cùng trong service graph Terminal node của subset cảnh báo và timestamp sớm nhất (vào lúc 09:42:01Z). Nó hoàn toàn khớp với lịch sử sự cố `INC-2025-11-08`.

**2. Ngưỡng Confidence & Auto-remediation**
Điểm confidence của `payment-svc` đạt mức tối đa 1.0 (do nó vừa có PageRank cao nhất, vừa có temporal score = 1.0). Với mức độ tự tin tuyệt đối này, team SRE có thể an tâm cấu hình auto-remediation (tự động rollback version hoặc scale connection pool 50 -> 100) mà không cần chờ người xác nhận.

**3. Edge case**
Tại cluster `c-003-000` (checkout-svc & search-svc đều cảnh báo), thuật toán gán root cause cho `checkout-svc`. Tuy nhiên, về mặt topology, hai service này khá độc lập ở layer API (chỉ nối chung qua catalog-db dưới data layer). Điểm graph không phản ánh được tắc nghẽn ở database chung. Đây là giới hạn của Graph-based RCA khi không có visibility đủ sâu ở mức query/tenant.

**4. Bonus Path**
Em không triển khai Bonus Path mà ưu tiên giữ cơ chế **Retrieval-only (Rule-based)**. Trong domain e-commerce với bộ dataset cảnh báo có các pattern lỗi rõ ràng và đã được gán metadata đầy đủ, phương pháp duyệt topology đồ thị kết hợp rule matching là đủ hiệu quả, đảm bảo MTTR cực nhanh với chi phí vận hành bằng 0.