# Postmortem: Tái hiện sự cố AWS S3 (2026-06-19)

> Báo cáo chuẩn Blameless SRE — không đổ lỗi cho cá nhân.

## Tóm tắt sự cố
Một thao tác bảo trì thường lệ nhằm khởi động lại hệ thống thanh toán (billing) đã vô tình làm sập cả hai hệ thống quan trọng khác (index và placement) do lỗi gõ nhầm lệnh (typo) mà không có bộ lọc (filter) chính xác. Việc này dẫn đến lỗi hoàn toàn về metadata và định vị dữ liệu, khiến toàn bộ hệ thống mô phỏng S3 ngừng hoạt động trong khoảng 4 giờ.

## Tác động (Impact)
- **Người dùng bị ảnh hưởng:** 100% request đều thất bại
- **Dịch vụ bị ảnh hưởng:** Billing, Index, Placement
- **Tác động doanh thu/SLA:** Ước tính thiệt hại 10.000 USD và vi phạm cam kết SLA
- **Thời gian kéo dài:** 2026-06-19 10:04 UTC đến 2026-06-19 14:04 UTC (4 tiếng)

## Dòng thời gian (Timeline - UTC)

| UTC | Sự kiện |
|-----|-------|
| 2026-06-19 10:04:32 | Bắt đầu bảo trì để khởi động lại dịch vụ billing. |
| 2026-06-19 10:04:35 | Lệnh lỗi được thực thi: `docker compose stop --timeout 1`. |
| 2026-06-19 10:04:36 | Sự kiện `docker`: `stop index-svc` |
| 2026-06-19 10:04:36 | Sự kiện `docker`: `stop placement-svc` |
| 2026-06-19 10:04:36 | Sự kiện `docker`: `stop billing-svc` |
| 2026-06-19 10:04:50 | Cảnh báo `prom`: `alert=ServiceDown state=firing` cho cả 3 dịch vụ. |
| 2026-06-19 10:06:00 | Bộ phận CSKH nhận lượng lớn báo cáo lỗi từ người dùng. |
| 2026-06-19 14:04:00 | Các dịch vụ đã được khởi động lại và xác minh hoạt động ổn định. |

## Nguyên nhân gốc rễ (Root cause)
Một đoạn script đã chạy lệnh `stop` trên toàn bộ môi trường compose thay vì chỉ nhắm mục tiêu vào dịch vụ `billing`, khiến cả dịch vụ `index` và `placement` bị sập cùng lúc.

## Yếu tố góp phần (Contributing factors)
1. Thiếu các cơ chế rào chắn (guardrails) hoặc bước xác nhận trước khi chạy các lệnh có tính phá hủy.
2. Các script triển khai liên kết quá chặt, khiến một lỗi gõ nhầm ảnh hưởng đến toàn bộ cụm.
3. Không có giới hạn tốc độ (rate-limiting) khi tắt dịch vụ, cho phép nhiều hệ thống quan trọng rớt mạng đồng thời.

## Phát hiện sự cố (Detection)
- **Phát hiện bằng cách nào?** Hệ thống cảnh báo Pipeline và Prometheus đã bắt được sự thay đổi trạng thái dịch vụ ngay lập tức.
- **MTTD (Thời gian phát hiện trung bình):** ~15 giây (thời gian để Prometheus kích hoạt cảnh báo).
- **Phân tích khoảng trống (Gap Analysis) của Pipeline khi tái hiện lỗi:**
  - Khoảng trống 1: AIOps pipeline không dự đoán được chuỗi sập dây chuyền; hệ thống chỉ cảnh báo *sau khi* tất cả dịch vụ đã sập.
  - Khoảng trống 2: Phân tích nguyên nhân (RCA) mất thời gian hơn vì lệnh gõ sai của người dùng không được ghi log trực tiếp vào luồng sự kiện của AIOps, chỉ có các tác dụng phụ của nó được ghi lại.

## Phản hồi sự cố (Response)
- **Hành động của người tiếp nhận đầu tiên:** Kiểm tra trạng thái container và nhận ra cả 3 container đều bị dừng thay vì chỉ 1 cái.
- **Thời gian giảm thiểu (Mitigate):** ~3 giờ để tìm ra quy trình re-index metadata sau khi hệ thống bị sập ngang (hard crash).
- **Thời gian giải quyết dứt điểm (Resolve):** 4 giờ.

## Action items (Việc cần làm)
| # | Hành động | Người phụ trách | Loại | Thời hạn |
|---|--------|-------|------|-----|
| 1 | Bắt buộc phải truyền tên dịch vụ cụ thể trong mọi lệnh bảo trì. | SRE Team | Phòng ngừa | 2026-06-25 |
| 2 | Tích hợp AIOps trace để theo dõi các lệnh thủ công gây thay đổi trạng thái dịch vụ. | AIOps Team | Phát hiện | 2026-07-01 |
| 3 | Tạo runbook tự động để phục hồi nhanh cho hệ thống index. | Core Dev | Giảm thiểu | 2026-07-10 |
