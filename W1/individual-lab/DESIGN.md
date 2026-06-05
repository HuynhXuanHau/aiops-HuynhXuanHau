# Detection Approach — DESIGN.md

## Approach tôi dùng

**Hybrid Multi-Stage Anomaly Detection Pipeline** kết hợp:
- Statistical anomaly detection (Z-score, baseline comparison)
- Univariate metrics monitoring
- Log-based error detection
- Voting mechanism để giảm false positives

## Tại sao chọn approach này

### Lợi ích cho streaming:
1. **Real-time processing**: Xử lý từng measurement ngay khi nhận, không cần accumulate toàn bộ dataset
2. **Phát hiện nhanh (Low TTD)**: Cảnh báo ngay khi thấy anomaly, không cần đợi
3. **Adaptable baseline**: Động tính toán baseline từ lịch sử gần đây (rolling window)
4. **Giảm false positives**: Voting mechanism yêu cầu ≥2 dấu hiệu trước khi alert
5. **Đơn giản và hiệu quả**: Không cần training, dùng statistics đơn giản

## Cách hoạt động

### Pipeline 7 bước:

1. **Ingest**: Nhận POST request với metrics + logs
2. **Buffer**: Lưu trữ metrics vào rolling window (30 lần đo gần nhất)
3. **Univariate Detection**: Kiểm tra từng metric:
   - Memory: Utilization > 80% HOẶC growing trend (>10MB/lần)
   - CPU: Usage > 60%
   - Traffic: Z-score > 2.5 std từ baseline
   - Errors: Z-score > 2.0 std HOẶC rate > 2%
   - Timeout: Rate > 0.5%
   - Latency: Z-score > 2.0 std
   - Queue: Depth > 20
4. **Log-based Detection**: Phát hiện FATAL/ERROR spikes
5. **Voting**: Combine signals, cần ≥2 votes cho alert
6. **Alert Generation**: Map anomalies → alert type (memory_leak, traffic_spike, dependency_timeout)
7. **Write Alert**: Ghi JSON line vào alerts.jsonl

### Anomaly → Alert Type Mapping:

| Detected Anomalies | Alert Type |
|-------|-----------|
| Memory utilization cao hoặc growing trend | `memory_leak` |
| Traffic spike, error rate spike | `traffic_spike` |
| Timeout rate cao | `dependency_timeout` |

## Parameters tôi chọn

| Parameter | Giá trị | Lý do |
|-----------|--------|--------|
| `WINDOW_SIZE` | 30 measurements | Đủ dữ liệu để detect trend mà không bị lag |
| `VOTE_THRESHOLD` | 2 votes | Reduce false positives; cần ≥2 metric signals |
| `MEMORY_THRESHOLD` | 80% | Thường OOM ở 85-90%, alert early |
| `CPU_THRESHOLD` | 60% | Dấu hiệu load cao trước khi saturate (100%) |
| `ERROR_RATE_THRESHOLD` | 2.0% | Bình thường < 0.8%, 2% là anomaly rõ |
| `TIMEOUT_THRESHOLD` | 0.5% | Bình thường < 0.4%, 0.5% là spike |
| `Z_SCORE_THRESHOLD` | 2.0-2.5 | Standard: >2 std là outlier |
| `BASELINE_WINDOW` | 100 measurements | Lịch sử đủ để tính baseline chính xác |

## Cải thiện nếu có thêm thời gian

1. **Seasonal decomposition (STL)**:
   - Hiện tại: Dùng rolling baseline
   - Cải thiện: Thêm STL để phân tách trend + seasonal + residual
   - Detect anomaly trên residual thay vì raw data

2. **Drain3 log template clustering**:
   - Hiện tại: Chỉ đếm ERROR/FATAL counts
   - Cải thiện: Cluster log patterns bằng Drain3, detect template spike

3. **Isolation Forest (multivariate)**:
   - Hiện tại: Chỉ univariate + voting
   - Cải thiện: IForest để detect complex multivariate anomalies

4. **Smoothing + Alert deduplication**:
   - Hiện tại: Alert mỗi khi detect anomaly
   - Cải thiện: Apply smoothing window (5-point median) để giảm noise
   - Deduplicate consecutive alerts cùng type

5. **LLM-based root cause analysis** (optional bonus):
   - Dùng Gemini API để generate root cause hypotheses dựa trên metric patterns

6. **Time-series forecasting**:
   - ARIMA/Prophet để predict expected values
   - Compare actual vs predicted để detect anomaly

---

## Summary

Approach này cân bằng **độ chính xác** (voting) + **tốc độ** (real-time processing) + **simplicity** (no ML training).
Phù hợp cho streaming use case và đủ để detect 3 loại fault chính: memory_leak, traffic_spike, dependency_timeout.
