# EOD Checkpoint W2-D2

**1. Confidence của top-1 trong cluster lớn nhất là bao nhiêu? Nếu phải set threshold để auto-rollback, bạn pick số nào?**
Confidence của top-1 (`payment-svc`) đạt mức 1.0. Nếu phải set một threshold cứng để hệ thống tự động chạy playbook mà không cần xác nhận thủ công, em sẽ chọn ngưỡng **0.80**. Lý do: Ngưỡng này đảm bảo ứng viên vừa nằm sâu ở tầng dependency (PageRank cao) vừa xuất hiện sớm trong chuỗi lỗi cascade, loại trừ được các victims downstream bị ảnh hưởng dây chuyền.

**2. Variant bạn chọn cho classifier (A/B/C)? Chạy thực tế ra sao? Trade-off?**
Em chọn **Variant A (Rule-based / kNN Retrieval)**. Khi chạy thực tế, thuật toán bám sát được baseline (map chính xác incident `INC-2025-11-08`) với độ trễ xử lý gần như tức thời. Trade-off của phương pháp này là tính linh hoạt: nó sẽ trả về kết quả kém nếu gặp sự cố chưa từng xảy ra trong 6 tháng qua, ngược lại với khả năng phỏng đoán của LLM.

**3. Pipeline xây dựng gần với product nào nhất trong industry? Lựa chọn đó có hợp lý?**
Pipeline này dựa sát theo triết lý của **Dynatrace Davis**, đặt Service Topology làm "source of truth" để truy vết lỗi. Lựa chọn này hợp lý với hệ thống e-commerce GeekShop do flow giao dịch tuần tự và ổn định (Edge -> Checkout -> Payment). Dựa trên graph giúp khoanh vùng cực nhanh kẻ gây tội thay vì tốn thời gian train các mô hình thống kê time-series phức tạp.