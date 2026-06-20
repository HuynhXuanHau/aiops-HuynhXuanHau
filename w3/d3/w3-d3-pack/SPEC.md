# SPEC: Nền tảng Xbrain AIOps

## 1. Tổng quan nền tảng
Nền tảng Xbrain AIOps là một công cụ phân tích nguyên nhân gốc rễ và phát hiện tự động, được thiết kế để giám sát các môi trường microservice. Phạm vi của nó bao gồm việc thu thập metric từ Prometheus, log sự kiện Docker và trace ứng dụng để nhanh chóng xâu chuỗi các điểm bất thường và tự động gọi (alert) đội trực hệ thống. Nền tảng không tự động khắc phục các lỗi mang tính phá hủy, mà sẽ cung cấp thông tin tinh gọn để giảm thiểu thời gian MTTD và MTTR.

## 2. Định nghĩa SLO (từ W3-D1)
- **Target SLO (Mục tiêu):** 99.9%
- **SLI:** Tỷ lệ phần trăm các request HTTP thành công tới frontend service trong vòng 30 ngày.
- **Error budget (Ngân sách lỗi):** 43.2 phút downtime mỗi tháng.
- **Burn-rate alert tiers (Cấp độ cảnh báo):** 
  - Đốt nhanh 14.4x (cửa sổ 1 giờ) -> Nhắn tin gọi kỹ sư ngay lập tức (Page).
  - Đốt chậm 1x (cửa sổ 3 ngày) -> Tạo Ticket.

## 3. Tech Stack Phát hiện + Tương quan + RCA (từ W1+W2)
- **Detector (Phát hiện):** Thuật toán Prophet và Isolation Forest, dữ liệu đầu vào từ Prometheus và Elasticsearch, đầu ra là schema cờ bất thường (anomaly flags).
- **Correlator (Tương quan):** Thuật toán DBSCAN, cửa sổ thời gian 5 phút, đầu ra là ID cụm (cluster ID) của các lỗi liên quan.
- **RCA (Nguyên nhân):** Thuật toán dò đồ thị nhân quả (PC Algorithm), lấy cấu trúc mạng lưới (topology) từ Zipkin, đầu ra là tỷ lệ xác suất của node lỗi gốc.

## 4. Xác minh độ tin cậy (từ W3-D2)
- **Lịch chạy Chaos engineering:** Hàng tuần.
- **Mục tiêu tỷ lệ lỗi bắt được/tổng lỗi:** > 90%
- **Steady-state signal (Tín hiệu cân bằng):** Kết hợp probe giả lập và metric nội bộ.

## 5. Mô hình Vận hành (từ W3-D3)
- **Mẫu báo cáo sự cố:** [postmortem.md](./postmortem.md)
- **Lịch trực (On-call):** Mô hình Follow-the-sun (ca 8 tiếng trải dài trên 3 múi giờ).
- **Lưu trữ quyết định kiến trúc (ADR):** [adr.md](./adr.md)

## 6. Mô hình chi phí (Cost model - từ W3-D3)
- **Chi phí hàng tháng:** 7,000.00 USD
- **Giá trị tiết kiệm hàng tháng:** 66,000.00 USD
- **Điểm hòa vốn (Số sự cố tránh được/tháng):** 1
- Xem chi tiết tại: [`cost_model.py`](./cost_model.py)

## 7. Rủi ro tồn đọng (Open risks)
- **Rủi ro 1:** Việc báo động quá nhiều trong các đợt triển khai dự kiến có thể khiến kỹ sư mắc hội chứng "nhờn cảnh báo" (alert fatigue).
- **Rủi ro 2:** Các thành phần của AIOps là điểm nghẽn duy nhất (single point of failure); nếu hệ thống telemetry bị sập, chúng ta sẽ mất hoàn toàn khả năng giám sát.
