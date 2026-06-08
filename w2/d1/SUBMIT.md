# Báo cáo Assignment W2-D1: Alert Correlation
Huỳnh Xuân Hậu - XB-DN26-129

## 7.3. Trả lời câu hỏi thiết kế (Design Trade-offs)

**1. Em chọn gap_sec bao nhiêu, vì sao?**
Em quyết định chọn mức khá chặt chẽ là `gap_sec = 30s`. Thay vì dùng window lớn (120s) có thể gom mọi thứ vào chung một cụm duy nhất, việc ép thời gian chênh lệch tối đa xuống 30s giúp em tách biệt được các giai đoạn của sự cố. Ví dụ, giai đoạn cảnh báo `warn` sớm của DB pool và giai đoạn sập hẳn (gây timeout/error_rate cao) sẽ được chia thành các cluster riêng biệt, giúp on-call engineer dễ dàng theo dõi dòng thời gian (timeline) sự cố phát triển như thế nào.

**2. Em chọn max_hop bao nhiêu, vì sao?**
Em giữ nguyên `max_hop = 2`. Sơ đồ kiến trúc của hệ thống có các service cốt lõi (payment, checkout, cart) thường gọi gián tiếp nhau qua tối đa 2 bước nhảy (ví dụ: edge-lb -> checkout -> payment). Việc giữ max_hop bằng 2 đảm bảo bắt được trọn vẹn "bán kính vụ nổ" (blast radius) về mặt cấu trúc hạ tầng. Việc hệ thống sinh ra 5 cụm (thay vì 1 cụm khổng lồ) chứng tỏ bộ lọc `gap_sec = 30s` ở trên đã làm rất tốt việc cắt đứt các hiệu ứng bắc cầu vô lý về mặt không gian.

**3. 1 alert ID đã bị “miss” (không match cluster nào) — tại sao?**
Alert bị "miss" (trở thành cụm mồ côi size=1) là `a-0013` của `recommender-svc` (hoặc `a-0016` của `search-svc`). Dù nó xảy ra cùng khoảng thời gian với sự cố nghẽn DB của `payment-svc`, nhưng trên đồ thị Topology, nhánh ML của recommender nằm cách quá xa (vượt số hop cho phép) và hoạt động độc lập với luồng API Gateway đang bị sập. Sự cố của nó là do "concurrent batch retrain" chứ không phải do hậu quả từ payment-svc.

**4. Nếu có 10000 alert thay vì 20, code của em sẽ chậm ở đâu?**
Nếu dùng đoạn code gốc (không tối ưu), chương trình sẽ bị thắt cổ chai ở vòng lặp quét từng cặp Service trong hàm `topology_group`. Gọi hàm tìm đường đi ngắn nhất (`nx.shortest_path_length`) cho mọi cặp sẽ ngốn chi phí thời gian lên tới $O(S^2)$. Để khắc phục, em đã tối ưu bằng Breadth-First Search (BFS) loang từ mỗi node (`nx.single_source_shortest_path_length`) kết hợp với tham số `cutoff`, giúp dừng quét ngay lập tức khi đạt đến max_hop.

---

## 8. EOD Checkpoint

**1. Vì sao fingerprint không include timestamp hay value? Cho ví dụ.**
Vì giá trị metric (VD: CPU 95%, rồi nhảy lên 98%) và timestamp sẽ liên tục trôi đi theo từng giây. Nếu đưa chúng vào fingerprint, mỗi lần hệ thống báo động sẽ tạo ra một fingerprint hoàn toàn mới. 
*Ví dụ:* Nếu cùng một lỗi nghẽn CPU báo 10 lần trong 2 phút, thay vì gom thành 1 cụm với `count = 10`, hệ thống sẽ đẻ ra 10 cụm rác khác nhau, khiến layer Dedup vô giá trị.

**2. Sự khác biệt giữa “duplicate” và “correlated” alert?**
- **Duplicate (Trùng lặp):** Là một triệu chứng lặp đi lặp lại nhiều lần. *Ví dụ:* Alert `a-0003` và `a-0008` đều báo lỗi `latency_p99_ms` của `payment-svc` vượt ngưỡng.
- **Correlated (Có quan hệ nhân quả):** Là các triệu chứng khác nhau nhưng chung nguồn gốc. *Ví dụ:* `payment-svc` cạn connection pool (`a-0001`) làm cho `checkout-svc` bị lỗi timeout (`a-0006`). 

**3. gap_sec = 30 vs gap_sec = 600 — mỗi cái ảnh hưởng output thế nào?**
- `gap_sec = 30`: Là một màng lọc khắt khe, giúp xé nhỏ các sự cố dài thành nhiều cluster chi tiết theo từng đợt bùng phát lỗi.
- `gap_sec = 600`: Màng lọc quá lỏng, dễ gây lỗi "gom nhầm" (false correlation) khi gom toàn bộ các sự cố không liên quan (như lỗi buổi sáng và lỗi lúc nghỉ trưa) vào chung 1 cụm sự cố khổng lồ.

**4. Correlator của em có gom recommender vào cluster chính không? Vì sao?**
Dạ không. Dù `recommender-svc` (alert `a-0013`) báo lỗi về CPU cùng lúc với luồng `payment-svc` sập (thoả mãn điều kiện Time-window), nhưng lớp lọc Topology đã loại nó ra vì `recommender-svc` không có cạnh nối trực tiếp (nằm ngoài phạm vi max_hop = 2) tới các service thuộc luồng thanh toán (critical path) đang bị lỗi.

**5. Limitation lớn nhất của topology grouping mà em nhận ra? Đề xuất khắc phục.**
Hạn chế lớn nhất của mô hình này là Service Graph hiện tại là một đồ thị "tĩnh" trên mức application, không phản ánh được hạ tầng vật lý bên dưới. Giả sử `payment-svc` và một service không liên quan là `search-svc` vô tình được deploy chung trên cùng một máy chủ (EC2). Khi EC2 rớt mạng, cả 2 cùng sập và báo lỗi, nhưng thuật toán sẽ không gom chúng lại do không có đường đi giữa 2 service này trên đồ thị.
*Đề xuất khắc phục:* Phải làm giàu đồ thị (Graph Enrichment) bằng cách bổ sung thêm các node hạ tầng (Host, Container, Database Instance, Switch) làm các đỉnh (vertices) liên kết chung.