# Thiết Kế Kiến Trúc: AIOps Model Serving Pipeline

## 1. Pipeline Architecture
Ứng dụng được thiết kế theo mô hình 3 lớp (Glue layer) bọc trong một HTTP REST API. 
* Tại giai đoạn khởi tạo (startup), hệ thống nạp đồ thị topology (`GRAPH`) và lịch sử sự cố (`HISTORY`) vào bộ nhớ (in-memory) dưới dạng các biến toàn cục để tránh I/O disk penalty cho mỗi request.
* Hàm xử lý chính trong `/incident` được bảo vệ hoàn toàn bởi khối `try/except` kèm cơ chế catch lỗi 422 tự động bằng Pydantic. Đầu ra được chuẩn hóa thành format dictionary để đảm bảo tầng logic không bị dính chặt (decoupled) vào framework web.

## 2. Latency Budget Breakdown
Tổng thời gian (Latency) cho mỗi request mục tiêu là dưới 10 giây (p99 < 10s). Trong đó:
* **Validation & Graph Ops (Correlate):** Chiếm ~50-100ms.
* **LLM Call (Root Cause Analysis):** Chiếm ~90% tổng thời gian (khoảng 2s - 8s).
Do đó, trọng tâm tối ưu (bottleneck) nằm ở khâu gọi LLM chứ không phải các thuật toán xử lý dữ liệu.

## 3. Production Concern: Fault Tolerance (Chống chịu lỗi mạng)
Sự cố phổ biến nhất trên production là mạng gọi API đến OpenAI bị treo (hang) làm vắt kiệt connection pool. Để xử lý rủi ro này, em đã thực hiện 2 cơ chế:
1. Thiết lập biến môi trường (Feature Flag) `AIOPS_USE_LLM`. Nếu OpenAI sập, chỉ cần gạt cờ này sang `False`, hệ thống sẽ skip bước LLM và chỉ dùng đồ thị để RCA.
2. Ép buộc Timeout tối đa (10 giây) cho mọi lệnh gọi mạng ra bên ngoài.

## 4. Trade-off: Lựa chọn FastAPI
Thay vì dùng Flask hay BentoML, em chọn FastAPI vì đặc thù hệ thống có bước gọi LLM (IO-bound). Cấu trúc `async` của FastAPI giúp hệ thống xử lý bất đồng bộ mượt mà. Pydantic validation đi kèm giúp chặn 100% các request sai format (thiết lập chuẩn HTTP 422) mà không cần code các block `if/else` cồng kềnh như trong Flask. BentoML thì quá nặng và thiên về Model-centric, không phù hợp cho pipeline linh hoạt này.