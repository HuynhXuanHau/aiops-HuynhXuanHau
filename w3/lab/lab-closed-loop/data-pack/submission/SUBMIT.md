# SUBMIT.md — Kết quả chạy 3 chaos scenarios

## Thông tin

- Họ tên: Huỳnh Xuân Hậu
- Decision engine: Rule-based (`RUNBOOK_MAP` trong `config.yaml`)
- Python: 3.12, uv 0.4.x
- Docker Compose: v2.27

---

## Scenario 1 — Action thành công (latency inject trên payment-svc)

**Lệnh inject:**
```bash
bash data-pack/scripts/inject_fault.sh latency ronki-payment-svc 500ms
```

**Log orchestrator (trích):**
```json
{"ts":"2026-06-17T09:12:01Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"HighLatency","service":"payment-svc","severity":"warning"}
{"ts":"2026-06-17T09:12:01Z","level":"INFO","event_type":"DECIDE_RUNBOOK","alertname":"HighLatency","service":"payment-svc","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-17T09:12:01Z","level":"INFO","event_type":"BLAST_RADIUS_OK","service":"payment-svc"}
{"ts":"2026-06-17T09:12:02Z","level":"INFO","event_type":"RUNBOOK_EXEC","script":"runbooks/restart_service.sh","service":"payment-svc","dry_run":true}
{"ts":"2026-06-17T09:12:02Z","level":"INFO","event_type":"RUNBOOK_RESULT","returncode":0,"stdout":"[DRY-RUN] would execute: docker restart ronki-payment-svc"}
{"ts":"2026-06-17T09:12:02Z","level":"INFO","event_type":"DRY_RUN_PASS","runbook":"runbooks/restart_service.sh","service":"payment-svc"}
{"ts":"2026-06-17T09:12:02Z","level":"INFO","event_type":"RUNBOOK_EXEC","script":"runbooks/restart_service.sh","service":"payment-svc","dry_run":false}
{"ts":"2026-06-17T09:12:08Z","level":"INFO","event_type":"RUNBOOK_RESULT","returncode":0,"stdout":"[restart_service] payment-svc is running."}
{"ts":"2026-06-17T09:12:08Z","level":"INFO","event_type":"ACTION_EXECUTED","runbook":"runbooks/restart_service.sh","service":"payment-svc"}
{"ts":"2026-06-17T09:12:08Z","level":"INFO","event_type":"VERIFY_START","service":"payment-svc","timeout_s":60}
{"ts":"2026-06-17T09:12:18Z","level":"INFO","event_type":"VERIFY_SAMPLE","sample":1,"latency_p99_ms":312.4,"up":1.0,"latency_ok":true,"up_ok":true}
{"ts":"2026-06-17T09:12:28Z","level":"INFO","event_type":"VERIFY_SAMPLE","sample":2,"latency_p99_ms":198.7,"up":1.0,"latency_ok":true,"up_ok":true}
{"ts":"2026-06-17T09:12:38Z","level":"INFO","event_type":"VERIFY_SAMPLE","sample":3,"latency_p99_ms":201.1,"up":1.0,"latency_ok":true,"up_ok":true}
{"ts":"2026-06-17T09:12:38Z","level":"INFO","event_type":"VERIFY_PASS","service":"payment-svc","samples":3}
{"ts":"2026-06-17T09:12:38Z","level":"INFO","event_type":"ACTION_SUCCESS","alertname":"HighLatency","service":"payment-svc","runbook":"runbooks/restart_service.sh"}
```

**Kết quả:** PASS. p99 latency giảm từ >500ms (lúc inject) về 201ms sau khi restart. Verify pass sau 3 sample liên tiếp.

---

## Scenario 2 — Action fail → rollback (checkout-svc killed, threshold thấp)

**Thiết lập:** Đặt tạm `verify_thresholds.latency_p99_max_ms: 1` trong `baseline.json` để verify luôn fail, kiểm tra rollback logic.

**Lệnh inject:**
```bash
bash data-pack/scripts/inject_fault.sh kill ronki-checkout-svc
```

**Log orchestrator (trích):**
```json
{"ts":"2026-06-17T09:25:10Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"InstanceDown","service":"checkout-svc","severity":"critical"}
{"ts":"2026-06-17T09:25:10Z","level":"INFO","event_type":"DECIDE_RUNBOOK","alertname":"InstanceDown","service":"checkout-svc","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-17T09:25:10Z","level":"INFO","event_type":"BLAST_RADIUS_OK","service":"checkout-svc"}
{"ts":"2026-06-17T09:25:10Z","level":"INFO","event_type":"DRY_RUN_PASS","runbook":"runbooks/restart_service.sh","service":"checkout-svc"}
{"ts":"2026-06-17T09:25:16Z","level":"INFO","event_type":"ACTION_EXECUTED","runbook":"runbooks/restart_service.sh","service":"checkout-svc"}
{"ts":"2026-06-17T09:25:16Z","level":"INFO","event_type":"VERIFY_START","service":"checkout-svc","timeout_s":60}
{"ts":"2026-06-17T09:25:26Z","level":"INFO","event_type":"VERIFY_SAMPLE","sample":1,"latency_p99_ms":145.2,"up":1.0,"latency_ok":false,"up_ok":true}
{"ts":"2026-06-17T09:26:16Z","level":"WARNING","event_type":"VERIFY_FAIL","service":"checkout-svc","samples":6}
{"ts":"2026-06-17T09:26:16Z","level":"WARNING","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc","rollback_runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-17T09:26:22Z","level":"INFO","event_type":"ROLLBACK_EXECUTED","service":"checkout-svc","rollback_runbook":"runbooks/restart_service.sh"}
```

**Kết quả:** PASS (rollback logic). Sau khi verify fail (latency 145ms > threshold 1ms), orchestrator tự động trigger rollback mà không cần can thiệp tay. `failure_count` tăng lên 1.

---

## Scenario 3 — Circuit breaker (3 consecutive failures)

**Thiết lập:** Giữ nguyên threshold thấp từ Scenario 2. Inject kill 3 lần, mỗi lần để orchestrator xử lý xong trước khi inject tiếp.

**Log orchestrator (trích — chỉ key events):**
```json
{"ts":"2026-06-17T09:35:01Z","level":"WARNING","event_type":"VERIFY_FAIL","service":"checkout-svc"}
{"ts":"2026-06-17T09:35:01Z","level":"WARNING","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc"}
{"ts":"2026-06-17T09:35:07Z","level":"INFO","event_type":"ROLLBACK_EXECUTED","service":"checkout-svc"}

{"ts":"2026-06-17T09:37:14Z","level":"WARNING","event_type":"VERIFY_FAIL","service":"checkout-svc"}
{"ts":"2026-06-17T09:37:14Z","level":"WARNING","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc"}
{"ts":"2026-06-17T09:37:20Z","level":"INFO","event_type":"ROLLBACK_EXECUTED","service":"checkout-svc"}

{"ts":"2026-06-17T09:39:42Z","level":"WARNING","event_type":"VERIFY_FAIL","service":"checkout-svc"}
{"ts":"2026-06-17T09:39:42Z","level":"WARNING","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc"}
{"ts":"2026-06-17T09:39:48Z","level":"INFO","event_type":"ROLLBACK_EXECUTED","service":"checkout-svc"}
{"ts":"2026-06-17T09:39:48Z","level":"ERROR","event_type":"CIRCUIT_BREAKER_HALT","consecutive_failures":3,"threshold":3,"message":"Automation halted. Manual intervention required."}

{"ts":"2026-06-17T09:41:00Z","level":"ERROR","event_type":"CIRCUIT_BREAKER_HALT","message":"Circuit open — polling suspended."}
{"ts":"2026-06-17T09:41:15Z","level":"ERROR","event_type":"CIRCUIT_BREAKER_HALT","message":"Circuit open — polling suspended."}
```

**Kết quả:** PASS. Sau failure thứ 3, orchestrator log `CIRCUIT_BREAKER_HALT` và không thực hiện thêm action nào. Vòng lặp poll tiếp tục chạy nhưng mỗi iteration chỉ log HALT và sleep — không trigger runbook.

---

## Điều học được

Checkpoint khó nhất là **Verify + Rollback**. Ban đầu tôi implement verify với 1 sample duy nhất và bị false positive (1 scrape may mắn trả về giá trị thấp ngay sau khi inject). Sau khi thêm `verify_min_samples: 3` (3 sample liên tiếp đều phải pass), kết quả ổn định hơn nhiều.

Blast-radius guard quan trọng hơn tôi nghĩ lúc đầu. Trong lần test thử trước khi hoàn thiện code, tôi để orchestrator restart payment-svc 8 lần trong 10 phút vì alert cứ firing lại sau mỗi restart (container cần 15-20s warm up nhưng Prometheus detect lại alert sau 30s). Sau khi thêm `max_restarts_per_service_per_hour: 5`, vấn đề này biến mất.

---

## Scenario 4 — Multi-step transactional rollback

**Lệnh inject:**
```bash
bash data-pack/scripts/inject_fault.sh kill ronki-api-gateway
```

**Log orchestrator (trích):**
```json
{"ts":"2026-06-17T10:01:00Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"MultiStepDeployAlert","service":"api-gateway"}
{"ts":"2026-06-17T10:01:00Z","level":"INFO","event_type":"DECIDE_RUNBOOK","alertname":"MultiStepDeployAlert","service":"api-gateway","runbook":"runbooks/multi_step_deploy.sh"}
{"ts":"2026-06-17T10:01:01Z","level":"INFO","event_type":"RUNBOOK_EXEC","script":"runbooks/multi_step_deploy.sh --step-a","service":"api-gateway"}
{"ts":"2026-06-17T10:01:05Z","level":"INFO","event_type":"RUNBOOK_EXEC","script":"runbooks/multi_step_deploy.sh --step-b","service":"api-gateway"}
{"ts":"2026-06-17T10:01:10Z","level":"ERROR","event_type":"TRANSACTIONAL_STEP_FAIL","step":"runbooks/multi_step_deploy.sh --step-c","service":"api-gateway","completed_before_failure":["runbooks/multi_step_deploy.sh --step-a","runbooks/multi_step_deploy.sh --step-b"]}
{"ts":"2026-06-17T10:01:11Z","level":"WARNING","event_type":"TRANSACTIONAL_ROLLBACK_STEP","step":"runbooks/multi_step_deploy.sh --rollback-b","service":"api-gateway"}
{"ts":"2026-06-17T10:01:15Z","level":"WARNING","event_type":"TRANSACTIONAL_ROLLBACK_STEP","step":"runbooks/multi_step_deploy.sh --rollback-a","service":"api-gateway"}
{"ts":"2026-06-17T10:01:19Z","level":"INFO","event_type":"TRANSACTIONAL_ROLLBACK_COMPLETE","service":"api-gateway","rolled_back":["runbooks/multi_step_deploy.sh --rollback-b","runbooks/multi_step_deploy.sh --rollback-a"]}
```

**Kết quả:** PASS. Orchestrator thực hiện bước A và B thành công. Khi bước C thất bại, orchestrator tự động trigger rollback theo thứ tự ngược lại (rollback-B, sau đó rollback-A) và log `TRANSACTIONAL_ROLLBACK_COMPLETE` với danh sách đúng.

---

## Scenario 5 — Concurrent alert race

**Lệnh inject:**
```bash
bash data-pack/scripts/inject_fault.sh --concurrent ronki-payment-svc ronki-inventory-svc
```

**Log orchestrator (trích):**
```json
{"ts":"2026-06-17T10:15:00Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"HighLatency","service":"payment-svc"}
{"ts":"2026-06-17T10:15:00Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"HighLatency","service":"inventory-svc"}
{"ts":"2026-06-17T10:15:00Z","level":"INFO","event_type":"DRY_RUN_PASS","runbook":"runbooks/restart_service.sh","service":"payment-svc"}
{"ts":"2026-06-17T10:15:00Z","level":"INFO","event_type":"DRY_RUN_PASS","runbook":"runbooks/restart_service.sh","service":"inventory-svc"}
{"ts":"2026-06-17T10:15:05Z","level":"INFO","event_type":"ACTION_EXECUTED","runbook":"runbooks/restart_service.sh","service":"payment-svc"}
{"ts":"2026-06-17T10:15:05Z","level":"INFO","event_type":"ACTION_EXECUTED","runbook":"runbooks/restart_service.sh","service":"inventory-svc"}
```

*Trong lúc service đang chạy, inject thêm alert cho payment-svc:*
```json
{"ts":"2026-06-17T10:15:02Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"HighLatency","service":"payment-svc"}
{"ts":"2026-06-17T10:15:02Z","level":"WARNING","event_type":"SERVICE_LOCK_BUSY","service":"payment-svc","message":"Another runbook is executing for this service; skipping duplicate"}
```

**Kết quả:** PASS. Hai service khác nhau xử lý đồng thời, `DRY_RUN_PASS` và `ACTION_EXECUTED` xuất hiện sát giờ nhau. Khi `payment-svc` nhận thêm alert trong lúc đang chạy, orchestrator drop bằng `SERVICE_LOCK_BUSY`.

---

## Scenario 6 — LLM hallucination defense

**Thiết lập:**
Thêm vào `config.yaml` ánh xạ `TestHallucination: "runbooks/nonexistent_runbook.sh"` và đảm bảo không có trong `runbook_registry`.

**Log orchestrator (trích):**
```json
{"ts":"2026-06-17T10:20:00Z","level":"INFO","event_type":"ALERT_DETECTED","alertname":"TestHallucination","service":"payment-svc"}
{"ts":"2026-06-17T10:20:00Z","level":"ERROR","event_type":"DECISION_VALIDATION_FAILED","bad_runbook":"runbooks/nonexistent_runbook.sh","alertname":"TestHallucination","raw_decision":"runbooks/nonexistent_runbook.sh","action":"escalate_no_auto_action"}
```

**Kết quả:** PASS. Orchestrator log lỗi validation và hủy thực thi lập tức. KHÔNG có bất kỳ sự kiện `DRY_RUN_PASS` hoặc `RUNBOOK_EXEC` nào xảy ra, và circuit breaker KHÔNG tăng counter.

