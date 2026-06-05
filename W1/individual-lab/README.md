# AIOps W1 Individual Lab — Setup & Usage Guide

## Quick Start

### 1. Install Dependencies

```bash
cd W1/individual-lab
uv pip install -r requirements.txt
```

### 2. Start the Pipeline (Terminal 1)

```bash
uv run python pipeline.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 3. Run Generator (Terminal 2)

```bash
# Replace with YOUR birthday in format YYYY-MM-DD
uv run python stream_generator.py --birthday 2005-08-17 --target http://localhost:8000/ingest
```

### 4. Monitor Alerts (Terminal 3)

```bash
# Watch alerts as they're generated
tail -f alerts.jsonl
# or with timestamp
tail -f alerts.jsonl | while read line; do echo "[$(date +'%H:%M:%S')] $line"; done
```

---

## How It Works

### Pipeline Flow:

1. **Generator** (stream_generator.py)
   - Emits metrics + logs every ~1 second
   - POST to your endpoint
   - Includes injected anomalies (fault, at some point during lab)

2. **Pipeline** (pipeline.py)
   - Receives POST /ingest
   - Analyzes metrics & logs
   - If anomaly detected → writes to `alerts.jsonl`

3. **Alert Format** (alerts.jsonl)
   ```json
   {"timestamp": "2026-06-05T10:23:45.000+00:00", "type": "memory_leak", "severity": "critical", "message": "Memory usage at 85% of limit"}
   ```

---

## Expected Anomalies

The generator will inject one of these at random time:

| Fault Type | Detectable As | Expected Alert |
|-----------|---------|-----------------|
| Memory leak | Memory growing + utilization > 80% | `memory_leak` |
| Traffic spike | Requests/sec spike, high CPU | `traffic_spike` |
| Dependency timeout | Timeout rate spike | `dependency_timeout` |

---

## Monitoring

### Check pipeline health:
```bash
curl http://localhost:8000/health
```

### View alert counts:
```bash
wc -l alerts.jsonl
```

### Filter alerts by type:
```bash
grep "memory_leak" alerts.jsonl | wc -l
grep "traffic_spike" alerts.jsonl | wc -l
grep "dependency_timeout" alerts.jsonl | wc -l
```

---

## Tuning Thresholds

Edit `pipeline.py` to adjust sensitivity:

```python
# Conservative (fewer alerts):
VOTE_THRESHOLD = 3
ERROR_RATE_THRESHOLD = 5.0

# Aggressive (more alerts):
VOTE_THRESHOLD = 1
ERROR_RATE_THRESHOLD = 1.0
```

---

## Troubleshooting

**Q: Generator says "connection refused"**
- A: Make sure pipeline is running first! Start pipeline BEFORE generator.

**Q: No alerts generated**
- A: 
  1. Check logs in terminal 1 (pipeline)
  2. Verify generator is actually sending data (check terminal 2)
  3. Try adjusting thresholds in pipeline.py

**Q: Too many false alerts**
- A: Increase VOTE_THRESHOLD or Z_SCORE_THRESHOLD in pipeline.py

**Q: Pipeline crashes**
- A: Check requirements.txt is installed: `uv pip install -r requirements.txt`

---

## Bonus Points

To earn bonus points, focus on:

1. **Correct fault type detection** (+1):
   - Your alert `type` matches actual fault
   - e.g., if generator injects memory_leak, alert should say `memory_leak`

2. **No false positives before fault** (+1):
   - Monitor alerts during first ~30 seconds
   - Should see no alerts before generator injects fault

3. **Fast detection (low TTD)** (+1):
   - Time from fault injection to your alert
   - Aim for <5 seconds

---

## Example Session

```bash
# Terminal 1: Start pipeline
$ uv run python pipeline.py
INFO:     Uvicorn running on http://0.0.0.0:8000

# Terminal 2: Start generator with your birthday
$ uv run python stream_generator.py --birthday 2005-08-17 --target http://localhost:8000/ingest
[INFO] Sending metrics to http://localhost:8000/ingest
[INFO] Normal operation...
[INFO] Normal operation...
[FAULT INJECTED] Memory leak starting at 2026-06-05T10:15:30.000+00:00
[INFO] Sending metrics...

# Terminal 3: Watch alerts
$ tail -f alerts.jsonl
{"timestamp": "2026-06-05T10:15:35.123+00:00", "type": "memory_leak", "severity": "critical", "message": "Memory usage at 82% of limit"}
```

---

## Files

- `pipeline.py` — Main streaming pipeline with detection logic
- `alerts.jsonl` — Output file with detected alerts (auto-created)
- `DESIGN.md` — Technical explanation of detection approach
- `requirements.txt` — Python dependencies

Good luck! 🚀
