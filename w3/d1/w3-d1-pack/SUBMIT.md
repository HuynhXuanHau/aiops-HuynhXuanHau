# W3-D1 Submission - <Điền tên của bạn vào đây>

## 3 thứ tôi học được
1. Sự khác biệt cốt lõi giữa SLA (Hợp đồng pháp lý), SLO (Cam kết nội bộ) và SLI (Chỉ số đo lường thực tế). Hiểu rằng SLO phải luôn lỏng hơn thông số hiện tại để có khoảng đệm (buffer) cho kỹ sư.
2. Sức mạnh của kiến trúc Multi-Window Multi-Burn-Rate (MWMBR). Sử dụng AND logic giữa Khung giờ dài (Long window) và Khung giờ ngắn (Short window) giúp dập tắt hoàn toàn báo động giả (False Positive) do nhiễu ngắn hạn, đồng thời cảnh báo tự ngắt rất nhanh khi sự cố qua đi.
3. Cách tính Error Budget dựa trên phần trăm SLO và làm thế nào để chuyển đổi Tỷ lệ lỗi (Error Rate) thành Tốc độ đốt ngân sách (Burn Rate) bằng phép chia cho (1 - SLO).

## 1 thứ vẫn chưa rõ
Mặc dù MWMBR rất mạnh mẽ, nhưng việc tìm ra Threshold và Window size tối ưu cho các hệ thống có lưu lượng truy cập (traffic) thay đổi mạnh mẽ giữa ngày và đêm vẫn còn khó khăn. Không rõ trong thực tế, các team có áp dụng Dynamic Threshold dựa trên traffic thực tế thay vì một hằng số tĩnh hay không.

## 1 trade-off trong SLO decision của tôi mà tôi không chắc
Tôi quyết định nới lỏng SLO của Frontend xuống 97% để loại bỏ nhiễu và báo động giả (giúp Pass được Validation script). Tuy nhiên, điều này đồng nghĩa với việc team cho phép tỷ lệ lỗi lên đến 3%. Tôi không chắc liệu mức 3% lỗi (hỏng UI, lỗi JS) có gây ra hậu quả quá lớn cho trải nghiệm khách hàng (Customer Experience) và làm rớt tỷ lệ chuyển đổi (Conversion Rate) trên trang E-commerce hay không.

## Validation report
- noise_reduction_pct: 93.0%
- mttd_delta_s: 0s
- false_negative: 0
- verdict: pass