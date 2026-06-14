# EOD Checkpoint - W2.D3

### 1. Latency thực của endpoint bạn ra sao? 
Sau khi bắn thử 20 request, em nhận thấy mức P50 rơi vào khoảng ~4s và P99 xấp xỉ 8.5s. 
* **Phase chiếm phần lớn:** Chắc chắn là bước gọi API ra LLM chiếm trên 90% ngân sách thời gian.
* **Khả năng Scale:** Các bước Validate dữ liệu và Serialize là fixed cost (gần như O(1)). Khâu gọi LLM cũng có độ trễ không phụ thuộc quá nhiều vào lượng log. Tuy nhiên, phase Graph Correlate sẽ scale linear nếu số lượng service và tập alert tăng lên đột biến.

### 2. LLM provider down hoặc 4 request đồng thời — endpoint handle ra sao?
* Khi ép tải với Apache Bench (`-c 4`), bottleneck đầu tiên em quan sát thấy chính là các luồng chờ I/O của OpenAI bị xếp hàng dài, làm tăng P99 latency đáng kể do giới hạn của single-worker (nếu dùng `--workers 1`). Nếu LLM bị down mà không có timeout, connection pool sẽ cạn sạch và API đứng cứng ngắc.
* **Fallback path:** Đã cài đặt một Feature flag `AIOPS_USE_LLM=false`. Khi gặp sự cố nghẽn mạng từ OpenAI, em có thể restart pod với biến này, hệ thống sẽ bỏ qua bước làm giàu dữ liệu bằng AI và trả về kết quả chỉ dựa trên suy diễn đồ thị (Graph-only).

### 3. /healthz và /readyz của bạn check gì? Tại sao tách riêng?
* `/healthz` chỉ check xem tiến trình (process) Uvicorn/FastAPI có đang sống hay không (Liveness). 
* `/readyz` thì check xem biến `GRAPH` và `HISTORY` đã có dữ liệu chưa (độ dài > 0) để chắc chắn app sẵn sàng nhận luồng dữ liệu của User (Readiness).
* Phải tách riêng vì mục đích khác nhau: Nếu `/healthz` fail, Kubernetes sẽ "giết" app và khởi động lại. Nếu `/readyz` fail, K8s chỉ ngắt đường ống đưa data vào.
* **Nếu LLM API down:** Endpoint `/readyz` **VẪN PASS**. Lý do: Ta không nên để trạng thái app của mình bị phụ thuộc vào uptime của bên thứ 3 như OpenAI. Nếu check LLM ở Readiness, khi OpenAI sập, Load Balancer sẽ đá app của ta ra khỏi mạng, dẫn đến việc mất luôn cả đường fallback chạy Graph-only mà ta đã thiết kế ở trên.