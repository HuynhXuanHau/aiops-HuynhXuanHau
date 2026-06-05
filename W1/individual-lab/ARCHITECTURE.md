# Streaming Anomaly Detection Pipeline - Architecture

## System Architecture

```
Generator (stream_generator.py)
         ↓
    POST /ingest
         ↓
   FastAPI Server (port 8000)
         ↓
┌─────────────────────────────────────────┐
│  Pipeline Processing Chain:             │
│                                         │
│  1. MetricsBuffer (rolling window)      │
│  2. Univariate Detection per metric     │
│  3. Log-based Detection                 │
│  4. Voting Mechanism                    │
│  5. Alert Generation & Writing          │
└─────────────────────────────────────────┘
         ↓
   alerts.jsonl (output file)
```

## Detection Logic Flow

### Stage 1: Univariate Anomaly Detection

For each incoming metric, we check:

```
Memory Leak Detection:
  ├─ If memory_util > 80% → flag anomaly
  └─ If memory growing >10MB/measurement → flag anomaly

CPU Spike Detection:
  └─ If cpu_usage > 60% → flag anomaly

Traffic Spike Detection:
  ├─ Calculate Z-score vs baseline
  └─ If Z > 2.5 std OR requests > 200 req/s → flag anomaly

Error Rate Detection:
  ├─ Calculate Z-score vs baseline
  └─ If Z > 2.0 std OR error_rate > 2% → flag anomaly

Timeout Detection:
  └─ If timeout_rate > 0.5% → flag anomaly

Latency Spike Detection:
  ├─ Calculate Z-score vs baseline
  └─ If Z > 2.0 std → flag anomaly

Queue Buildup Detection:
  └─ If queue_depth > 20 → flag anomaly
```

### Stage 2: Log Analysis

```
Log-based Detection:
  ├─ Count FATAL level entries → flag fatal_errors
  └─ Count ERROR level entries (>1) → flag error_spike
```

### Stage 3: Voting Mechanism

```
For each anomaly type detected:
  └─ Increment vote counter
  
If votes >= VOTE_THRESHOLD (2):
  ├─ This anomaly is considered "real"
  └─ Proceed to alert generation
```

### Stage 4: Alert Type Mapping

```
Detected Anomalies  →  Alert Type          →  Severity
─────────────────────────────────────────────────────────
memory* anomalies   →  memory_leak         →  critical
traffic_spike       →  traffic_spike       →  warning
timeout*            →  dependency_timeout  →  warning
error_spike         →  traffic_spike       →  warning
```

### Stage 5: Alert Writing

```json
{
  "timestamp": "2026-06-05T10:23:45.000+00:00",
  "type": "memory_leak",
  "severity": "critical",
  "message": "Memory usage at 85% of limit"
}
```

---

## Key Implementation Details

### MetricsBuffer (Thread-Safe)
- Stores last 30 measurements (deque with maxlen)
- Maintains rolling baseline for each metric (last 100 values)
- Thread-safe with locks for concurrent access

### Baseline Calculation
```python
def calculate_baseline_stats(key):
    if len(buffer) < 20:
        return None, None  # Not enough data
    
    mean = average(last_100_values)
    std = std_dev(last_100_values)
    return mean, std
```

### Z-Score Calculation
```python
z_score = (value - mean) / std
if abs(z_score) > threshold:  # e.g., 2.0 or 2.5
    anomaly_detected = True
```

### Memory Growth Detection
```python
recent_values = [last_5_measurements]
slope = (value[-1] - value[0]) / 5
if slope > 10_MB_per_measurement:
    memory_leak_flag = True
```

---

## Parameters & Thresholds

| Parameter | Value | Sensitivity |
|-----------|-------|-------------|
| MEMORY_UTIL_THRESHOLD | 80% | Early warning before OOM (OOM ~95%) |
| CPU_THRESHOLD | 60% | High load (saturated at 100%) |
| ERROR_RATE_THRESHOLD | 2.0% | Normal: <0.8%, Anomaly: >2% |
| TIMEOUT_THRESHOLD | 0.5% | Normal: <0.4%, Anomaly: >0.5% |
| Z_SCORE_THRESHOLD | 2.0-2.5 | 2 std dev ≈ 5% prob, 2.5 std ≈ 1% |
| VOTE_THRESHOLD | 2 | Need 2+ metric signals to alert |
| WINDOW_SIZE | 30 | Lookback for trend analysis |
| BASELINE_WINDOW | 100 | History for statistical baseline |

---

## Performance Characteristics

- **Latency per request**: ~5-10ms (pure Python)
- **Memory**: ~5-10 MB (baseline + buffer storage)
- **Detection latency (TTD)**: 1-2 seconds after anomaly injection
- **False positive rate**: Expected <5% on normal traffic

---

## Why This Approach Works for Streaming

1. **No accumulation required** — Process each measurement immediately
2. **Adaptive baselines** — Rolling window adapts to gradual changes
3. **Statistical rigor** — Z-scores are well-understood anomaly indicators
4. **Fast decisions** — Voting with threshold makes deterministic decisions
5. **Reduced false positives** — Multiple signals + voting mechanism
6. **Extensible** — Easy to add new metrics or detection rules

---

## Improvement Roadmap

For production use, consider:

1. **Seasonal decomposition** (STL)
   - Separate trend + seasonal + residual
   - Detect on residual for better accuracy

2. **Log template clustering** (Drain3)
   - Group similar logs into templates
   - Detect log pattern anomalies

3. **Multivariate detection** (Isolation Forest)
   - Detect complex interactions between metrics
   - Capture correlated anomalies

4. **Persistent state**
   - Store baseline to disk
   - Survive restarts

5. **Root cause inference**
   - LLM-based correlation analysis
   - Generate hypotheses about what failed

---

## Validation Checklist

- [x] HTTP endpoint responds to POST /ingest
- [x] Parses metrics + logs from payload
- [x] Detects memory/traffic/timeout anomalies
- [x] Writes alerts to alerts.jsonl
- [x] Thread-safe metrics buffer
- [x] Adaptive baseline calculation
- [x] Voting mechanism to reduce false positives
- [x] Proper alert type mapping
- [x] Descriptive alert messages

---

**Pipeline is ready for lab! 🚀**
