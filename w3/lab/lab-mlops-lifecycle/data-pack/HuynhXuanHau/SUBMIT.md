# SUBMIT.md — Reflection: MLOps Lifecycle Lab (Updated with Real Execution Data)

## Câu 1: Drift threshold bạn chọn là bao nhiêu và tại sao?

Threshold được chọn là **0.15** (15% số lượng thuộc tính bị lệch phân phối theo Evidently DataDriftPreset).

**Biện luận dựa trên thực nghiệm:**
- **Xác định nhiễu nền (Noise floor):** Khi chạy thử nghiệm `drift_detector` trên chính tập dữ liệu chuẩn `baseline.csv` (chia phân tách tỷ lệ 70/30), chỉ số sai lệch tự nhiên đo được chỉ là `0.04`. Việc chọn ngưỡng `0.15` (gấp gần 3.75 lần nhiễu nền) là khoảng cách an toàn, giúp hệ thống không bị kích hoạt báo động sai (False Positive) bởi các biến động nhỏ mang tính chu kỳ (ví dụ: lượng traffic thay đổi giữa ngày và đêm).
- **Độ nhạy thực tế:** Khi hệ thống tiếp nhận tệp dữ liệu lỗi `drifted.csv`, điểm số Drift Score thực tế đo được vọt lên tới `1.0000` (vượt xa ngưỡng `0.15`), giúp hệ thống lập tức nhận diện chính xác sự cố lệch phân phối để kích hoạt chu trình xử lý tiếp theo.

---

## Câu 2: Điều gì xảy ra nếu model v2 sau retrain lại tệ hơn v1?

Hệ thống đã được thiết kế một cơ chế phòng vệ 2 lớp cực kỳ nghiêm ngặt nhằm triệt tiêu hoàn toàn rủi ro mô hình mới hoạt động kém làm ảnh hưởng tới môi trường Production:

1. **Lớp 1 - Manual Approval Gate:** Sau khi tái huấn luyện (Retrain), mô hình mới sẽ được đăng ký tạm thời dưới nhãn `staging`. Hệ thống sẽ hiển thị bảng thông số tóm tắt (Drift Score, Anomaly Rate) và dừng lại chờ kỹ sư MLOps phê duyệt thủ công qua dòng lệnh `Promote staging → production? [y/N]`. Nếu kỹ sư từ chối hoặc không phản hồi, mô hình lỗi sẽ bị cô lập tại `staging`.
2. **Lớp 2 - Post-Deploy Monitoring & Auto-Rollback (Đã chạy thực tế):** Khi người dùng đồng ý duyệt (`y`), mô hình v3 được đưa lên `production`. Ngay lập tức, hệ thống kích hoạt chu trình hậu kiểm tự động (Post-deploy evaluation) trên tập dữ liệu kiểm thử thực tế `post_deploy_eval.csv`. 
   - **Kết quả thực nghiệm:** Ngay tại chu kỳ đầu tiên (`Cycle 01/24`), chỉ số **Precision** của mô hình v3 chỉ đạt **0.4000**, vi phạm nghiêm trọng ngưỡng chất lượng tối thiểu là **0.65**.
   - **Hành động phản ứng:** Cơ chế giám sát tự động kích hoạt **AUTO-ROLLBACK**. Hệ thống tự động đẩy mô hình v3 vào kho lưu trữ (`@archived`), khôi phục phiên bản ổn định trước đó (v2) quay lại nhãn `@production`, và gửi lệnh `POST /reload` tới API để khôi phục trạng thái an toàn trong chưa đầy 30 giây mà không gây gián đoạn hệ thống.

---

## Câu 3: Sự khác biệt giữa data drift và concept drift?

- **Data Drift (Phân phối dữ liệu thay đổi):** Là sự thay đổi ở phía đầu vào hệ thống — toán học gọi là $P(X)$ thay đổi, trong khi mối quan hệ bản chất giữa đầu vào và đầu ra $P(Y|X)$ giữ nguyên. *Ví dụ:* Do có chiến dịch kích cầu hoặc tích hợp bên thứ ba, lượng Request Per Second (`rps`) tăng đột biến hoặc độ trễ hệ thống (`latency_p99`) tịnh tiến từ 120ms lên 156ms. Lúc này, mô hình cũ sẽ nhận diện nhầm các giá trị "bình thường mới" này là bất thường (Anomaly).
- **Concept Drift (Bản chất khái niệm thay đổi):** Là sự thay đổi trong mối quan hệ giữa đầu vào và đầu ra — tức $P(Y|X)$ thay đổi. *Ví dụ:* Trước đây độ trễ 200ms được coi là thảm họa hệ thống (Anomaly), nhưng sau khi hạ tầng core được nâng cấp lớn, độ trễ 200ms trở thành trạng thái hoạt động bình thường của hệ thống. Dữ liệu đầu vào không đổi nhưng nhãn đầu ra đã đảo ngược hoàn toàn.

**Cơ chế phát hiện trong bài Lab:**
Tệp `drift_detector.py` sử dụng thư viện **Evidently AI** để thực hiện các bài kiểm tra thống kê (như kiểm định định lượng khoảng cách Wasserstein) trên từng cột thuộc tính độc lập để phát hiện **Data Drift**. Đối với **Concept Drift**, do môi trường Production không có nhãn thực tế ngay lập tức (Ground-truth labels), hệ thống giám sát gián tiếp (Proxy) bằng cách theo dõi xu hướng tỷ lệ bất thường (`anomaly_rate_trend`) được log tập trung trên giao diện MLflow theo thời gian.

---

## Câu 4: Tại sao blue-green swap quan trọng hơn replace file trực tiếp?

Việc ghi đè trực tiếp tệp mô hình vật lý (như file `.pkl`) lên server đang chạy là một lỗ hổng vận hành lớn vì:
- **Xung đột ghi đọc (Race Condition):** API `serve.py` có thể đang đọc dở tệp mô hình cũ để xử lý một Request của khách hàng đúng lúc tiến trình Retrain ghi đè file mới lên $\rightarrow$ lỗi hỏng luồng dữ liệu (Corrupted read), gây sập server (Crash) hoặc trả về kết quả dự đoán sai lệch.
- **Mất khả năng quay xe (No Rollback):** Tệp cũ bị xóa vĩnh viễn, nếu mô hình mới phát sinh lỗi, hệ thống hoàn toàn tê liệt và buộc phải tốn thời gian build/redeploy lại từ đầu.

**Giải pháp Blue-Green atomic swap qua MLflow Registry:**
Trong bài lab này, cả hai phiên bản mô hình cũ và mới luôn tồn tại song song, biệt lập trong kho lưu trữ của MLflow Model Registry. Khi tiến hành cập nhật, nhãn định danh (`alias: production`) được hoán đổi ở tầng logic của MLflow một cách tức thời (Atomically). FastAPI (`serve.py`) vẫn phục vụ các Request đang nghẽn bằng mô hình cũ một cách an toàn, và chỉ nạp mô hình mới vào bộ nhớ RAM khi nhận được lệnh gọi webhook `POST /reload`. Nếu xảy ra sự cố (như tình huống Precision sụt giảm xuống `0.4000` ở trên), việc Rollback chỉ đơn giản là đổi lại nhãn logic trên MLflow và kích hoạt reload, đưa hệ thống về trạng thái an toàn trong vài giây.

---

## Câu 5: Nếu automate approval gate, dùng metric gì và threshold nào?

Dựa trên dữ liệu thu thập trực tiếp từ vòng đời chạy thử nghiệm, để tự động hóa hoàn toàn cổng phê duyệt (Automate Approval Gate) mà không cần con người can thiệp, chúng ta cần áp dụng chiến lược kết hợp đa chỉ số (Combined Mode) trên một tập dữ liệu thẩm định độc lập (`holdout.csv` hoặc `post_deploy_eval.csv`) với các quy tắc nghiêm ngặt:

1. **Ngưỡng chất lượng tối thiểu (Hard Quality Threshold):**
   - **Precision (Độ chính xác):** Phải $\ge 0.65$. (Mô hình v3 bị loại bỏ tự động chính vì vi phạm điều kiện tiên quyết này khi chỉ đạt `0.4000`). Ngưỡng này đảm bảo hệ thống không phát tín hiệu báo động giả quá nhiều, gây kiệt quệ cho đội ngũ vận hành on-call.
2. **Kiểm soát độ lệch hành vi (Behavioral Delta Check):**
   - **Tỷ lệ bất thường biến động:** $|Anomaly\_Rate_{new} - Anomaly\_Rate_{old}| \le 0.05$. Biên độ lệch 5% này nhằm đảm bảo mô hình mới sau khi học phân phối mới không bị rơi vào trạng thái quá cực đoan: hoặc là gắn nhãn lỗi cho toàn bộ traffic (`Anomaly Rate` quá cao) hoặc là quá bảo thủ không phát hiện ra sự cố nào (`Anomaly Rate` xấp xỉ 0).
3. **Điều kiện biên về phân phối (Distribution Boundary):**
   - **Holdout Drift Score:** Phải $< 0.15$. Đảm bảo mô hình mới hoạt động tốt trên tập dữ liệu đích và không bị Overfitting nghiêm trọng.

**Cơ chế kích hoạt:** Nếu mô hình Candidate vượt qua toàn bộ các bài kiểm tra trên, hệ thống sẽ tự động thực hiện lệnh promote lên thẳng `production`. Ngược lại, nếu vi phạm bất kỳ chỉ số nào, hệ thống lập tức thực thi lệnh **Auto-Rollback** về phiên bản an toàn trước đó và gửi cảnh báo khẩn cấp (Alert) cho kỹ sư hệ thống kiểm tra nguyên nhân cốt lõi.
