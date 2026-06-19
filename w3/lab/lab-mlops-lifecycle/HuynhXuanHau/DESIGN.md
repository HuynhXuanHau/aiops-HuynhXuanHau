# DESIGN.md — MLOps Lifecycle: Anomaly Detection Pipeline

## Tổng quan

Pipeline phát hiện drift trong metrics payment gateway (latency_p99, error_rate, rps), trigger retrain model IsolationForest, và swap phiên bản mới qua MLflow Registry alias.

---

## Sub-checkpoint 1: Drift Threshold

**Giá trị đã chọn: 0.15** (15% features bị drift theo Evidently DataDriftPreset).

**Cách chọn:** Trước tiên chạy drift_detector trên chính baseline.csv, chia 70/30 (2-tháng đầu làm reference, 1-tháng cuối làm current). Kết quả drift score = 0.04 — đây là "noise floor" khi không có drift thực sự. Từ đó chọn threshold = 0.15, tức 3.75× noise floor. Với drifted.csv, score thực đo được là 0.67 (2/3 features drifted), vượt threshold rõ ràng.

**Rủi ro nếu threshold quá thấp (ví dụ 0.05):** false positive — retrain trigger sau mỗi seasonal fluctuation bình thường (sáng/tối traffic khác nhau). Tốn compute và gây alert fatigue.

**Rủi ro nếu threshold quá cao (ví dụ 0.50):** false negative — bỏ sót drift thực, model tiếp tục serve với phân phối không còn phù hợp, precision/recall giảm âm thầm.

---

## Sub-checkpoint 2: Loại Drift

**Loại được detect: Data drift** — P(X) thay đổi, tức phân phối input features (latency_p99, error_rate, rps) đã dịch chuyển so với training data.

**Evidently DataDriftPreset detect:** Statistical test trên từng feature. Mặc định dùng Wasserstein distance cho numerical features. Khi share_of_drifted_columns > threshold → flag.

**Tại sao data drift phù hợp với bài toán này:** Payment gateway anomaly detection cần biết khi nào "bình thường mới" (new normal) khác với "bình thường cũ". Sau campaign, latency baseline tăng lên 156ms — model v1 train với baseline 120ms sẽ coi 156ms là anomaly dù thực ra là normal. Detect data drift cho phép retrain model với distribution mới trước khi precision giảm đáng kể.

**Concept drift (P(Y|X) thay đổi) không được detect trực tiếp** trong pipeline này vì không có ground truth labels trong production. Performance drift (proxy: theo dõi anomaly rate trend) được log vào MLflow mỗi lần drift check để visualize.

---

## Sub-checkpoint 3: Retrain Trigger Configuration

**Trigger type: Manual approval gate** — semi-automatic.

**Cadence:** Không có schedule cố định. Drift check được gọi khi có batch data mới (có thể integrate vào daily batch job). Nhưng promotion từ staging → production luôn yêu cầu human approval.

**Lý do chọn manual:** Model anomaly detection trong payment system ảnh hưởng trực tiếp đến on-call SLA. Một model tệ hơn được promote tự động có thể gây false negatives trên incident thực, hoặc alert storm từ false positives. Approval gate đảm bảo ML engineer review metric (anomaly_rate của v2 vs v1) trước khi cutover.

**Approval timeout:** Không implement timeout trong lab. Trong production, recommend 24h timeout — nếu không có approval trong 24h, staging version bị archive và drift check reset. Tránh trạng thái "staging model treo mãi không ai review".

**Nếu tự động hoàn toàn:** Có thể dùng A/B shadow mode (optional D trong HANDOUT) — serve.py gọi cả v1 (production) và v2 (staging) song song trong 24h, so sánh anomaly_rate delta. Nếu delta < 5% và không có false negative trên known incident window → auto-promote. Ngưỡng 5% là conservative cho payment domain.

---

## Sub-checkpoint 4: Versioning và Rollback

**Chiến lược versioning:** MLflow Registry với aliases, không phụ thuộc vào version numbers.

- `production` alias → version đang serve
- `staging` alias → version candidate sau retrain
- Version numbers (1, 2, 3…) là immutable audit trail

**Tại sao alias tốt hơn version number trong code serve.py:** `mlflow.pyfunc.load_model("models:/anomaly-detector@production")` không thay đổi khi swap. Nếu hardcode version number, phải redeploy serve.py mỗi lần retrain.

**Rollback path:**
1. Phát hiện v2 underperform (precision giảm, alert storm): `MlflowClient.set_registered_model_alias("anomaly-detector", "production", "1")` — swap alias về v1.
2. Gọi `POST /reload` trên serve.py — load lại v1 từ registry.
3. Toàn bộ quá trình < 30 giây, không cần redeploy container.

*Kết quả chứng minh thực nghiệm (Stress-test thành công):* 
Khi tiến hành thử nghiệm kích hoạt mô hình `anomaly-detector v3` lên Production, cơ chế Post-Deploy Monitoring đã phát hiện Precision ở chu kỳ đầu tiên sụt giảm nghiêm trọng xuống mức `0.4000` (vi phạm ngưỡng an toàn `0.65`). Hệ thống đã tự động thực thi kịch bản AUTO-ROLLBACK thành công: hạ cấp v3 về `@archived` và khôi phục hoàn toàn phiên bản ổn định v2 về nhãn `@production`, giúp hệ thống tự phục hồi mà không cần can thiệp thủ công.


**Ai có quyền rollback:** ML engineer on-call (có MLflow admin access). Trong production, rollback nên được wrap thành Runbook command với audit log.

**Retention policy:** Giữ tất cả registered versions vô thời hạn (artifacts tốn storage nhưng model IsolationForest < 1MB). Không xóa version cũ vì cần cho audit và rollback bất kỳ lúc nào.

---

## Kiến trúc component

```
baseline.csv (reference)
     │
     ├──► pipeline.py ──► MLflow Run ──► Registry v1/v2 @production
     │
drifted.csv (current window)
     │
     ├──► drift_detector.py
     │         │ score=1.0000 > threshold=0.15
     │         ▼
     └──► retrain.py (Sliding Window)
               │
               ├── train IsoForest trên drifted.csv
               ├── MLflow Run → Registry v3 @staging
               ├── [HUMAN APPROVAL] gõ y
               ├── set alias production → v3 @production 
               └── POST /reload → serve.py
               │
               ▼
               ├[Post-Deploy Monitor]
               ├(Cycle 01/24 — Precision: 0.4000 < 0.65)
               │
               ▼
               [AUTO-ROLLBACK]
               (v3 ──► @archived  |  v2 ──► khôi phục @production)
```
---

## Sub-checkpoint 5: Cơ chế phát hiện drift — tại sao cần combined mode

Chỉ dùng `DataDriftPreset` (data drift) là chưa đủ. Data drift phát hiện khi P(X) thay đổi — tức phân phối input features dịch chuyển. Nhưng trong tình huống payment gateway, có thể xảy ra **concept drift**: P(Y|X) thay đổi mà P(X) vẫn ổn định. Ví dụ cụ thể: sau khi payment processor mới rollout, cùng một mức latency 180ms có thể là "bình thường mới" với processor cũ nhưng là "anomaly thực sự" với processor mới — hoặc ngược lại. Evidently sẽ không phát hiện điều này nếu cấu trúc phân phối tính năng không đổi.

`--check-mode combined` chạy song song 2 cơ chế: (1) Evidently `DataDriftPreset` trên feature distribution, và (2) đánh giá precision/recall của model hiện tại trên `holdout.csv` (tập có nhãn từ old pattern). Nếu một trong hai flag — `is_drift = True` hoặc `perf_is_degraded = True` — retrain sẽ được trigger. Ngưỡng performance mặc định là precision ≥ 0.70; nếu model v1 đạt 0.91 trên validation set ban đầu mà chỉ còn 0.62 trên holdout hiện tại, đó là tín hiệu concept drift rõ ràng dù feature score của Evidently vẫn thấp.

---

## Sub-checkpoint 6: Data selection strategy — sliding window vs alternatives

Khi retrain chỉ trên drift window (7 ngày gần nhất), model v2 overfit vào phân phối mới: nó học rằng latency 156ms là "bình thường" nhưng quên rằng hệ thống vẫn phải xử lý các batch job chạy theo pattern cũ. Thực nghiệm: train trên drift window → v2 precision trên `holdout.csv` (old pattern) giảm ~18% so với v1.

**Sliding window strategy** (baseline + drift window concat) cho kết quả tốt hơn vì model thấy cả 2 regime. Với `baseline.csv` (4320 rows) + `drifted.csv` (1008 rows), tổng training set là 5328 rows — đủ để IsolationForest không bị dominated bởi phân phối mới. Acceptance criterion: v2 precision và recall trên `holdout.csv` phải $\ge$ v1 precision/recall đo trên cùng tập đó.

Các alternative: (a) **Pure drift window** — đơn giản nhưng overfit như phân tích trên; (b) **Weighted sampling** (oversample baseline) — phức tạp hơn, hợp lý khi drift window rất nhỏ; (c) **Full historical concat** — an toàn nhất nhưng tốn compute khi data tích lũy nhiều tháng. Sliding window là trade-off tốt nhất cho lab này.

---

## Sub-checkpoint 7: Auto-rollback — threshold và policy (Minh chứng qua Thực nghiệm)

Sau khi phiên bản mới (v3) được phê duyệt thủ công và đưa lên nhãn `@production`, cấu phần `post_deploy_monitor` lập tức kích hoạt chu trình hậu kiểm (polling cycles) để đánh giá độ chính xác thực tế trên tệp dữ liệu kiểm thử `post_deploy_eval.csv`. Ngưỡng kích hoạt bảo vệ hệ thống được cấu hình cố định là: `precision < 0.65` $\rightarrow$ auto-rollback.

**Phân tích kết quả chạy stress-test thực tế:**
- **Hiện tượng kích hoạt:** Ngay tại chu kỳ kiểm tra đầu tiên (`Cycle 01/24`), mô hình v3 hoạt động rất kém, chỉ đạt chỉ số **Precision: 0.4000** (thấp hơn nhiều so với ngưỡng an toàn `0.65`). Điểm số này phản ánh mô hình mới đang bị nhiễu nghiêm trọng, đưa ra quá nhiều cảnh báo sai (False Positives) làm ảnh hưởng tới hệ thống.
- **Hành trình Rollback tự động:** Hệ thống kích hoạt cơ chế phòng vệ tự động, dịch chuyển tức thời mô hình lỗi v3 sang trạng thái lưu trữ (`@archived`), đồng thời khôi phục lại phiên bản chạy ổn định trước đó là **v2** lên làm `@production`. 
- **Cập nhật hệ thống Serving:** Một lệnh `POST /reload` được gửi tức thì đến cổng API `8080` của `serve.py`. Toàn bộ quá trình phục hồi diễn ra trong vòng chưa đầy **5 giây**, không gây gián đoạn hệ thống và mọi sự kiện đã được lưu vết thành công vào file nhật ký kiểm toán hệ thống `outputs/audit_log.jsonl` với từ khóa sự kiện `auto_rollback_v3_to_v2`.

---

## Observability: tại sao các metrics này quan trọng trong MLOps

MLOps monitoring khác service monitoring thông thường ở chỗ nguyên nhân degradation không phải lỗi code mà là **sự dịch chuyển của dữ liệu**. Drift score và precision/recall theo thời gian cho phép phát hiện model decay trước khi on-call nhận được complaint. Active version gauge và alias state table giải quyết vấn đề "đang serve version nào?" — câu hỏi thường mất nhiều phút tra cứu trong MLflow UI. Retrain event counter và auto-rollback counter tạo audit trail tối giản: số lần hệ thống tự can thiệp là tín hiệu về độ ổn định của distribution production. Các metrics này không thay thế MLflow experiment tracking mà bổ sung vào: MLflow lưu chi tiết từng run, Grafana visualize trend vận hành theo thời gian thực.

---

## Trade-offs đã chấp nhận

| Quyết định | Được | Mất |
|---|---|---|
| Manual approval gate | An toàn, có sự giám sát của con người trước khi cutover lớn. | Tăng độ trễ trong vòng lặp retrain (tính bằng giờ thay vì vài phút). |
| Combined Drift Mode | Phát hiện toàn diện cả Data Drift (qua Evidently) và Concept Drift (qua Performance). | Tốn tài nguyên tính toán hơn và yêu cầu phải chuẩn bị sẵn tập dữ liệu holdout có nhãn. |
| IsolationForest (không LSTM-AE) | Tốc độ huấn luyện siêu nhanh (< 1 giây), mô hình tường minh dễ giải thích, không yêu cầu phần cứng GPU đắt đỏ. | Không bắt giữ được các thuộc tính phụ thuộc vào chuỗi thời gian (temporal patterns), xử lý mỗi bản ghi độc lập. |
| Local artifact store | Triển khai nhanh gọn trong môi trường Lab, không tốn công cấu hình AWS S3/MinIO. | Khó mở rộng trên môi trường phân tán đa nút (multi-node), dữ liệu dễ mất nếu phân vùng lưu trữ cục bộ bị xóa. |