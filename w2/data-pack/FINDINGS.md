# KẾT LUẬN

## 1. Hàm tương đồng đã chọn cho Layer 2 và lý do

Em đã chọn một hàm tương đồng kết hợp bao gồm:
- chồng chéo mẫu log (log templates) — so sánh các thông điệp log đã được chuẩn hoá với `log_signatures` trong lịch sử,
- khớp bất thường trace trên cùng một cạnh (`from`/`to`) sử dụng tỉ lệ sai khác p99 và độ tương đồng tỉ lệ lỗi,
- độ tương đồng Jaccard trên danh sách dịch vụ bị ảnh hưởng.

Điểm cuối cùng là tổng có trọng số: 45% log similarity, 35% trace similarity, 20% service overlap. Nếu lịch sử không có trace signatures, có cơ chế fallback phù hợp.

Các phương án thay thế đã cân nhắc:
- chỉ dùng metrics (metrics-only): tính toán đơn giản nhưng theo đề bài, metrics đơn lẻ là tín hiệu yếu; nhiều ca đánh giá (E01, E06, E08) cần cả logs và traces.
- embedding dày / tương đồng ngữ nghĩa của log: hấp dẫn nhưng với khoảng ~30 sự cố lịch sử dễ bị overfit và tăng độ phức tạp.

Lý do thực nghiệm cho lựa chọn hybrid: các ca E01 và E03 đều cần khớp mẫu lỗi thô và cạnh trace bất thường; engine đã nhận ra mẫu cạn pool của `payment-svc` và mẫu rò bộ nhớ ở E03 từ cấu trúc text+trace, cho kết quả tốt mà không cần embedding đầy đủ.

## 2. Outcome-weighted voting thay đổi thứ tự ứng viên thế nào so với xếp hạng thuần tương đồng?

Outcome-weighted voting ưu tiên các hành động đã thành công trong lịch sử trên các vụ việc tương tự, thay vì chỉ chọn hành động từ hàng xóm gần nhất về mặt tương đồng.

Ví dụ cụ thể: E05.
- Bằng chứng thô trong E05 có cả lỗi pool-exhaustion và dấu hiệu deadlock.
- Xếp hạng thuần similarity sẽ đẩy `rollback_service:payment-svc` lên cao vì khớp template log mạnh với các vụ pool-exhaustion trước đó.
- Khi đưa trọng số kết quả (outcome) vào, các neighbor có kết quả `partial` hoặc `failed` bị phạt, nên `page_oncall` vẫn giữ vị thế cạnh tranh và cuối cùng thắng vì an toàn hơn.

Báo cáo audit cho E05 cho thấy `rollback_service` có tương đồng mạnh, nhưng utility thực tế bị giảm bởi hồ sơ outcome lịch sử và chi phí; trong khi `page_oncall` có similarity thấp hơn nhưng utility kỳ vọng dài hạn cao hơn.

## 3. Giải thích đầy đủ phép tính EV (expected value) cho một ca đánh giá

Em chọn E05 vì nó minh hoạ rõ ràng sự đánh đổi trong quyết định.

Tập ứng viên trong `audit.jsonl` cho E05:
- `rollback_service` trên `payment-svc`
- `increase_pool_size` trên `payment-svc`
- `page_oncall`

Trọng số và điểm:
- `rollback_service:payment-svc` score = 1.3365, normalized score = 0.3541, `p_success` = 0.4479.
- `increase_pool_size:payment-svc` score = 1.035, normalized score = 0.2742, `p_success` = 0.3929.
- `page_oncall` score = 1.2109, normalized score = 0.3208, `p_success` = 0.4246.

Chi phí và blast radius:
- `rollback_service`: cost 10, blast radius 1 → utility = 0.4479 - 0.4 - 0.07 = -0.0221.
- `increase_pool_size`: cost 1, blast radius 1 → utility = 0.3929 - 0.04 - 0.07 = 0.2829.
- `page_oncall`: cost 0, blast radius 0 → utility = 0.4246.

Quyết định:
- `rollback_service` bị trừ mạnh do chi phí và tự tin không đủ, dẫn tới utility âm.
- `page_oncall` thắng vì có utility kỳ vọng cao nhất trong các ứng viên an toàn.
- Kết quả này trùng khớp với outcome mong đợi cho E05.

## 4. Khi nào engine chọn escalate (`page_oncall`) thay vì tự động hành động?

Engine đã chọn `page_oncall` cho các ca:
- `E02` (hết hạn TLS / vấn đề chứng chỉ ở `edge-lb`)
- `E04` (sự cố DNS / hạ tầng)
- `E05` (bằng chứng hỗn hợp, utility auto-action không an toàn)
- `E06` (bằng chứng mâu thuẫn, auto-recovery quá rủi ro)
- `E07` (mẫu mới / OOD)
- `E08` (mơ hồ giữa cascade/leaf-root, page là lựa chọn an toàn)

Đúng hay không? Đúng — bộ grader báo `8/8` chính xác, và các lựa chọn này khớp với `eval/expected.json`.

## 5. Loại sự cố nào có khả năng làm hỏng engine nhất?

Chế độ lỗi khả dĩ nhất là một lớp sự cố hoàn toàn mới mà:
- không có khớp mẫu log trong lịch sử,
- không có cạnh trace bất thường trùng lặp,
- và nguyên nhân gốc rễ ở cấp dịch vụ khác với mọi thứ từng thấy trước đó.

Trong trường hợp này engine vẫn có thể fallback về `page_oncall`, nhưng có nguy cơ đánh giá thấp khả năng một hành động tự động an toàn nếu sự cố mới thực ra có analog tốt.

Cải tiến cụ thể: bổ sung OOD detector với ngưỡng similarity được hiệu chỉnh, kết hợp lần quét thứ hai dùng suy luận root_service và phương pháp cluster template rộng hơn. Tôi không triển khai OOD calibration đầy đủ do giới hạn thời gian; ưu tiên là pipeline đánh giá 8/8 hoạt động.

## Tóm tắt điều hành

- **Mục tiêu:** xây dựng engine đề xuất hành động khắc phục dựa trên bằng chứng lịch sử, có khả năng giải thích và an toàn (escalate khi không đủ tin cậy).
- **Kết quả:** engine chạy end-to-end trên `eval/E01..E08.json` và tạo `audit.jsonl` gồm 8 bản ghi; grading báo `Correct: 8/8`.
- **Hạn chế chính:** chưa có OOD calibration, chưa có biểu đồ reliability cho confidence, ngưỡng hiện là heuristic.

## Kỹ thuật & chi tiết triển khai

1) Feature extraction (`features.py`)
	- Log templates: chuẩn hóa số/UUID, tách token, chọn top-N templates theo tần suất và độ tương đồng TF-lite.
	- Trace signatures: gom theo cặp (from,to), tính tỉ lệ p99 so với baseline và delta tỉ lệ lỗi.
	- Dịch vụ ảnh hưởng: danh sách dịch vụ có lỗi hoặc trace bất thường.

2) Retrieval (`retrieval.py`)
	- Hàm similarity = 0.45*log_sim + 0.35*trace_sim + 0.20*service_jaccard.
	- `OUTCOME_WEIGHT = {"success":1.0,"partial":0.6,"failed":0.1}` áp cho phiếu của mỗi neighbor.
	- Điều chỉnh mục tiêu dịch vụ: nếu lịch sử chỉ hành động lên một dịch vụ khác nhưng `root_service` trùng khớp, map action về `root_service` để tăng độ an toàn.

3) Decision (`decision.py`)
	- Chuyển score → `p_success` bằng chuẩn hóa Min-Max trên tập candidate của incident.
	- Utility = `p_success - alpha*cost_min - beta*blast_radius_services` với `alpha=0.04`, `beta=0.07` (heuristic).
	- Safety gates:
		- Nếu `normalized_score` < 0.18 → `page_oncall` (OOD / low consensus).
		- Nếu best utility ≤ 0 → `page_oncall`.

## Metrics đánh giá & khả năng tái tạo

- Các lệnh eval đã dùng (chạy trong `d:\AWS\Xbrain\AIOps\w2\data-pack`):

```powershell
python engine.py decide --incident eval/E01.json --history incidents_history.json --actions actions.yaml
python grade.py --audit audit.jsonl --expected eval/expected.json
(Get-Content audit.jsonl).Count  # -> 8
```

- Kết quả chính: `Correct: 8/8` so với `eval/expected.json`.

## Ví dụ mục audit (mẫu)

```json
{
    "incident_id":"E03",
    "selected_action":"restart_service",
    "params":{"service":"payment-svc"},
    "confidence":0.73,
    "evidence":{"top_3_neighbors":[...],"consensus_score":0.61}
}
```

## Hạn chế, rủi ro và đề xuất cải thiện

- OOD & Calibration: thêm bộ test OOD và mô-đun threshold calibration (ví dụ bootstrap trên lịch sử) để chọn ngưỡng `normalized_score` tự động.
- Confidence calibration: vẽ reliability diagram và dùng Platt scaling / isotonic regression trên `p_success` lịch sử.
- Audit trail: `audit.jsonl` đã có bằng chứng; có thể mở rộng với trường `explainability` (đoạn trace, template đã khớp).
- Safety: thêm whitelist/blacklist cho hành động tự động theo dịch vụ nhạy cảm.