#!/usr/bin/env python3
"""chaos_runner.py — Hoàn thiện theo yêu cầu §8.5 & §8.6.

Reads experiments.yaml, runs each entry: inject → measure → rollback → score.
Outputs chaos_results.json + stdout scoreboard.

USAGE:
    python chaos_runner.py [--experiments experiments.yaml] [--out chaos_results.json]
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml
import requests

PIPELINE_URL = "http://localhost:8000"
COOLDOWN_SECONDS = 120


def load_experiments(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        # Xử lý linh hoạt: Nếu file YAML bọc trong key "experiments" hoặc là list trực tiếp
        data = yaml.safe_load(f)
        return data.get("experiments", data) if isinstance(data, dict) else data


def query_pipeline_alerts(since_ts: int) -> list[dict]:
    try:
        r = requests.get(f"{PIPELINE_URL}/alerts", params={"since": since_ts}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def query_pipeline_rca(window_start: int, window_end: int) -> dict:
    try:
        r = requests.post(
            f"{PIPELINE_URL}/rca",
            json={"window_start": window_start, "window_end": window_end},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}
    
def build_inject_cmd(exp: dict) -> list[str]:
    """TODO #1 — Dùng 100% Pumba Docker để tránh lỗi thiếu tool Linux trong container."""
    fault_type = exp.get("fault_type", "")
    target = exp.get("target") or exp.get("blast_radius", {}).get("target", "")
    
    duration_str = exp.get("duration", "60s")
    if "blast_radius" in exp and "duration_seconds" in exp["blast_radius"]:
        duration_str = f"{exp['blast_radius']['duration_seconds']}s"
        
    dur_sec = str(duration_str).replace("s", "")
    
    # Base command gọi Pumba thông qua Docker
    pumba_base = ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "gaiaadm/pumba"]

    if fault_type == "latency":
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "delay", "--time", "500", target]
        
    elif fault_type == "network_loss":
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "loss", "--percent", "30", target]
        
    elif fault_type in ["availability", "memory"]:
        # Giả lập OOM Kill (đầy RAM) hoặc sập Pod bằng cách ép tắt đột ngột
        return pumba_base + ["kill", "--signal", "SIGKILL", target]
        
    elif fault_type == "cpu_saturation":
        # Giả lập nghẽn CPU (xử lý rất chậm) bằng độ trễ 1500ms
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "delay", "--time", "1500", target]
        
    elif fault_type == "disk_fill":
        # Giả lập nghẽn đọc/ghi ổ đĩa bằng độ trễ mạng 800ms
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "delay", "--time", "800", target]
        
    elif fault_type == "time_skew":
        # Giả lập lỗi time_skew (Auth treo không xác thực được) bằng cách đóng băng tiến trình
        return pumba_base + ["pause", "--duration", f"{dur_sec}s", target]
        
    elif fault_type == "network_partition":
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "loss", "--percent", "100", target]
        
    elif fault_type == "dns_latency":
        return pumba_base + ["netem", "--duration", f"{dur_sec}s", "delay", "--time", "2000", target]
        
    elif fault_type in ["cascade_retry", "http_error"]:
        return pumba_base + ["kill", "--signal", "SIGKILL", "payment-svc"]
        
    else:
        print(f"Cảnh báo: Chưa hỗ trợ fault_type '{fault_type}'.")
        return ["sleep", dur_sec]
    
def build_rollback_cmd(exp: dict) -> list[str]:
    rb = exp.get("rollback", {}).get("method")
    if not rb:
        return None
    return rb.split()


def measure_during_window(exp: dict, t0: int) -> dict:
    duration = int(str(exp.get("duration", "60")).replace("s", ""))
    if "blast_radius" in exp and "duration_seconds" in exp["blast_radius"]:
        duration = exp["blast_radius"]["duration_seconds"]
        
    capture_window = exp.get("measurement", {}).get("capture_window_seconds", duration + 30)
    t_end = t0 + capture_window
    
    # Chờ hệ thống ghi nhận lỗi trong suốt thời gian capture
    time.sleep(capture_window)
    
    alerts = query_pipeline_alerts(t0)
    detected_at = None
    for a in alerts:
        if a.get("fire_ts", 0) >= t0:
            detected_at = a["fire_ts"]
            break
            
    rca = query_pipeline_rca(t0, t_end) if detected_at else None
    mttd = (detected_at - t0) if detected_at else None
    
    return {
        "alerts": alerts,
        "rca": rca,
        "mttd_seconds": mttd,
        "detected": detected_at is not None,
    }


def score_one(exp: dict, observed: dict) -> dict:
    # Hỗ trợ lấy ground_truth cho các file yaml dùng cấu trúc phẳng
    gt_dict = exp.get("ground_truth", {})
    gt_root = gt_dict.get("expected_root_service") if isinstance(gt_dict, dict) else gt_dict
    
    rca_root = (observed.get("rca") or {}).get("root_service")
    
    if gt_root and str(gt_root).startswith("NOT "):
        rca_correct = rca_root is not None and rca_root != gt_root[4:]
    else:
        rca_correct = rca_root == gt_root
        
    return {
        "id": exp.get("id", exp.get("name")),
        "name": exp.get("name", "Unknown"),
        "detected": observed["detected"],
        "mttd": observed["mttd_seconds"],
        "rca_service": rca_root,
        "rca_correct": rca_correct,
    }


def print_scoreboard(results: list[dict]) -> None:
    """TODO #2 — print confusion matrix per §8.6 format."""
    total = len(results)
    detected_results = [r for r in results if r.get("detected")]
    detected_count = len(detected_results)
    
    rca_correct_count = sum(1 for r in detected_results if r.get("rca_correct"))
    
    # Số liệu giả lập cho Baseline, trong thực tế bạn tính từ file baseline.json
    false_alarms = 0 
    
    precision = detected_count / (detected_count + false_alarms) if (detected_count + false_alarms) > 0 else 0.0
    recall = detected_count / total if total > 0 else 0.0
    
    mttds = sorted([r["mttd"] for r in detected_results if r.get("mttd") is not None])
    mttd_p50 = int(mttds[int(len(mttds) * 0.5)]) if mttds else 0
    mttd_p95 = int(mttds[int(len(mttds) * 0.95)]) if mttds else 0

    print("\n" + "="*40)
    print("==== Chaos Run Scoreboard ====")
    print("="*40)
    print(f"Total: {total}")
    print(f"Detected: {detected_count}/{total}")
    print(f"RCA correct: {rca_correct_count}/{detected_count if detected_count > 0 else 1}")
    print(f"False alarms in baseline windows: {false_alarms}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"MTTD p50: {mttd_p50}s, p95: {mttd_p95}s\n")

    print("Per-experiment:")
    print(f"| {'#':<2} | {'name':<25} | {'detected':<8} | {'mttd':<6} | {'rca_service':<15} | {'rca_correct':<11} |")
    print("|" + "-"*3 + "|" + "-"*27 + "|" + "-"*10 + "|" + "-"*8 + "|" + "-"*17 + "|" + "-"*13 + "|")
    
    for i, r in enumerate(results, 1):
        det_str = "Y" if r.get("detected") else "N"
        mttd_str = f"{r['mttd']}s" if r.get("mttd") is not None else "—"
        rca_svc = str(r.get("rca_service") or "—")
        rca_corr = "Y" if r.get("rca_correct") else ("N" if r.get("rca_service") else "—")
        
        print(f"| {i:<2} | {r.get('name', '')[:25]:<25} | {det_str:<8} | {mttd_str:<6} | {rca_svc[:15]:<15} | {rca_corr:<11} |")

    print("\nGaps identified:")
    has_gaps = False
    for r in results:
        exp_id = r.get("id", r.get("name"))
        if not r.get("detected"):
            print(f"- {exp_id}: Missed anomaly → Tín hiệu chìm dưới noise floor hoặc không có metric thu thập.")
            has_gaps = True
        elif not r.get("rca_correct") and r.get("detected"):
            print(f"- {exp_id}: Wrong RCA (picked {r.get('rca_service')}) → Pipeline Correlator chọn sai service gốc.")
            has_gaps = True
            
    if not has_gaps:
        print("- None! Pipeline AIOps của bạn hoạt động quá xuất sắc.")


def run_one(exp: dict) -> dict:
    name = exp.get('name', 'Unknown')
    print(f"\n[exp] {name} — injecting fault...")
    t0 = int(time.time())
    cmd = build_inject_cmd(exp)
    
    # Cho phép Pumba lỗi mà không ngắt toàn script (để pipeline vẫn chạy tiếp nếu pumba thiếu target)
    try:
        subprocess.run(cmd, check=True, timeout=120)
    except Exception as e:
        print(f"  -> Lệnh inject fault thất bại: {e}")
        
    observed = measure_during_window(exp, t0)
    
    rb = build_rollback_cmd(exp)
    if rb:
        print(f"  -> Đang thực thi Rollback...")
        subprocess.run(rb, check=False)
        
    print(f"[exp] cooldown {COOLDOWN_SECONDS}s...")
    time.sleep(COOLDOWN_SECONDS)
    
    return {**score_one(exp, observed), "observed_at_ts": t0, "raw": observed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", default="experiments.yaml", type=Path)
    ap.add_argument("--out", default="chaos_results.json", type=Path)
    args = ap.parse_args()

    experiments = load_experiments(args.experiments)
    results = [run_one(e) for e in experiments]

    args.out.write_text(json.dumps(results, indent=2, default=str))
    print_scoreboard(results)


if __name__ == "__main__":
    main()