"""
Streaming Anomaly Detection Pipeline for AIOps W1 Lab
Detects memory leaks, traffic spikes, and dependency timeouts in real-time
"""

from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import json
import uvicorn
from collections import deque
import numpy as np
from scipy import stats
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
ALERTS_FILE = "alerts.jsonl"
WINDOW_SIZE = 30  # Keep last 30 measurements
VOTE_THRESHOLD = 2  # Need at least 2 votes to flag univariate anomaly

# Anomaly detection thresholds
MEMORY_UTILIZATION_THRESHOLD = 0.80  # 80% of limit
CPU_SPIKE_THRESHOLD = 60  # CPU > 60%
ERROR_RATE_THRESHOLD = 2.0  # 5xx rate > 2%
TIMEOUT_RATE_THRESHOLD = 0.5  # Timeout rate > 0.5%
REQUEST_SPIKE_THRESHOLD = 200  # req/s > 200

# For baseline calculation
BASELINE_WINDOW = 100
MIN_BASELINE_SAMPLES = 20

app = FastAPI()

class MetricsBuffer:
    """Thread-safe buffer for streaming metrics"""
    def __init__(self, window_size=WINDOW_SIZE):
        self.lock = threading.Lock()
        self.metrics = deque(maxlen=window_size)
        self.baseline = {}
        
    def add(self, metric_data):
        with self.lock:
            self.metrics.append(metric_data)
            
    def get_metrics(self):
        with self.lock:
            return list(self.metrics)
    
    def update_baseline(self, key, value):
        with self.lock:
            if key not in self.baseline:
                self.baseline[key] = deque(maxlen=BASELINE_WINDOW)
            self.baseline[key].append(value)

buffer = MetricsBuffer()

def calculate_baseline_stats(key):
    """Calculate mean and std for a metric key"""
    with buffer.lock:
        if key not in buffer.baseline or len(buffer.baseline[key]) < MIN_BASELINE_SAMPLES:
            return None, None
        data = list(buffer.baseline[key])
    
    mean = np.mean(data)
    std = np.std(data)
    return mean, std

def detect_univariate_anomalies(metrics):
    """
    Detect anomalies per metric using statistical methods
    Returns: dict with anomaly flags and vote counts
    """
    anomalies = {}
    vote_counts = {}
    
    timestamp = metrics.get("timestamp")
    metric_values = metrics.get("metrics", {})
    
    # Memory leak detection
    memory_usage = metric_values.get("memory_usage_bytes", 0)
    memory_limit = metric_values.get("memory_limit_bytes", 2_000_000_000)
    memory_util = memory_usage / memory_limit if memory_limit > 0 else 0
    
    if memory_util > MEMORY_UTILIZATION_THRESHOLD:
        anomalies["memory_leak"] = True
        vote_counts["memory_leak"] = vote_counts.get("memory_leak", 0) + 1
    
    # Check for memory growing trend (compare recent vs older)
    recent_metrics = buffer.get_metrics()
    if len(recent_metrics) >= 5:
        recent_values = [m["metrics"].get("memory_usage_bytes", 0) for m in recent_metrics[-5:]]
        if len(recent_values) >= 2:
            slope = (recent_values[-1] - recent_values[0]) / 5
            if slope > 10_000_000:  # Growing >10MB per measurement
                anomalies["memory_leak"] = True
                vote_counts["memory_leak"] = vote_counts.get("memory_leak", 0) + 1
    
    # CPU spike detection
    cpu_usage = metric_values.get("cpu_usage_percent", 0)
    if cpu_usage > CPU_SPIKE_THRESHOLD:
        anomalies["cpu_spike"] = True
        vote_counts["cpu_spike"] = vote_counts.get("cpu_spike", 0) + 1
    
    # Traffic spike detection
    requests_per_sec = metric_values.get("http_requests_per_sec", 0)
    mean_requests, std_requests = calculate_baseline_stats("http_requests_per_sec")
    
    if mean_requests is not None and std_requests > 0:
        z_score = (requests_per_sec - mean_requests) / std_requests
        if z_score > 2.5:  # >2.5 std devs above mean
            anomalies["traffic_spike"] = True
            vote_counts["traffic_spike"] = vote_counts.get("traffic_spike", 0) + 1
    elif requests_per_sec > REQUEST_SPIKE_THRESHOLD:
        anomalies["traffic_spike"] = True
        vote_counts["traffic_spike"] = vote_counts.get("traffic_spike", 0) + 1
    
    # Error rate spike detection
    error_rate = metric_values.get("http_5xx_rate", 0)
    mean_errors, std_errors = calculate_baseline_stats("http_5xx_rate")
    
    if mean_errors is not None and std_errors > 0:
        z_score = (error_rate - mean_errors) / std_errors
        if z_score > 2.0:
            anomalies["error_spike"] = True
            vote_counts["error_spike"] = vote_counts.get("error_spike", 0) + 1
    elif error_rate > ERROR_RATE_THRESHOLD:
        anomalies["error_spike"] = True
        vote_counts["error_spike"] = vote_counts.get("error_spike", 0) + 1
    
    # Timeout detection
    timeout_rate = metric_values.get("upstream_timeout_rate", 0)
    if timeout_rate > TIMEOUT_RATE_THRESHOLD:
        anomalies["dependency_timeout"] = True
        vote_counts["dependency_timeout"] = vote_counts.get("dependency_timeout", 0) + 1
    
    # Latency spike detection
    p99_latency = metric_values.get("http_p99_latency_ms", 0)
    mean_latency, std_latency = calculate_baseline_stats("http_p99_latency_ms")
    
    if mean_latency is not None and std_latency > 0:
        z_score = (p99_latency - mean_latency) / std_latency
        if z_score > 2.0:
            anomalies["latency_spike"] = True
            vote_counts["latency_spike"] = vote_counts.get("latency_spike", 0) + 1
    
    # Queue depth spike detection
    queue_depth = metric_values.get("queue_depth", 0)
    if queue_depth > 20:
        anomalies["queue_buildup"] = True
        vote_counts["queue_buildup"] = vote_counts.get("queue_buildup", 0) + 1
    
    # Update baseline for future comparisons
    for key, value in metric_values.items():
        buffer.update_baseline(key, value)
    
    return anomalies, vote_counts

def detect_log_anomalies(logs, timestamp):
    """
    Detect anomalies in logs (FATAL/ERROR spikes)
    """
    anomalies = {}
    
    fatal_count = sum(1 for log in logs if log.get("level") == "FATAL")
    error_count = sum(1 for log in logs if log.get("level") == "ERROR")
    
    if fatal_count > 0:
        anomalies["fatal_errors"] = True
    
    if error_count > 1:
        anomalies["error_spike"] = True
    
    return anomalies

def should_alert(anomalies, vote_counts):
    """
    Determine if we should fire an alert
    Uses voting mechanism: need at least VOTE_THRESHOLD votes for univariate anomalies
    """
    alert_types = []
    
    for anomaly_type, is_anomaly in anomalies.items():
        if is_anomaly:
            votes = vote_counts.get(anomaly_type, 0)
            if votes >= VOTE_THRESHOLD:
                alert_types.append(anomaly_type)
    
    return alert_types

def map_anomaly_to_alert_type(anomaly_types):
    """Map detected anomalies to alert types (memory_leak, traffic_spike, dependency_timeout)"""
    if not anomaly_types:
        return None
    
    # Priority mapping
    if any("memory" in a for a in anomaly_types):
        return "memory_leak"
    elif any("traffic" in a or "request" in a for a in anomaly_types):
        return "traffic_spike"
    elif any("timeout" in a or "dependency" in a for a in anomaly_types):
        return "dependency_timeout"
    elif any("error" in a for a in anomaly_types):
        return "traffic_spike"  # Error spike indicates traffic/load issue
    else:
        return anomaly_types[0]

def generate_alert_message(anomaly_types, metrics):
    """Generate descriptive alert message"""
    metric_values = metrics.get("metrics", {})
    
    messages = []
    for anomaly_type in anomaly_types:
        if "memory" in anomaly_type:
            memory_util = metric_values.get("memory_usage_bytes", 0) / metric_values.get("memory_limit_bytes", 1)
            messages.append(f"Memory usage at {memory_util*100:.1f}% of limit")
        elif "traffic" in anomaly_type:
            req_sec = metric_values.get("http_requests_per_sec", 0)
            messages.append(f"Traffic spike detected: {req_sec:.1f} req/s")
        elif "timeout" in anomaly_type:
            timeout_rate = metric_values.get("upstream_timeout_rate", 0)
            messages.append(f"Upstream timeout rate: {timeout_rate*100:.2f}%")
        elif "error" in anomaly_type:
            error_rate = metric_values.get("http_5xx_rate", 0)
            messages.append(f"Error rate spike: {error_rate*100:.2f}%")
    
    return " | ".join(messages) if messages else "Anomaly detected"

def write_alert(timestamp, alert_type, severity, message):
    """Write alert to alerts.jsonl"""
    alert = {
        "timestamp": timestamp,
        "type": alert_type,
        "severity": severity,
        "message": message
    }
    
    try:
        with open(ALERTS_FILE, "a") as f:
            f.write(json.dumps(alert) + "\n")
        logger.info(f"Alert fired: {alert_type} - {message}")
    except Exception as e:
        logger.error(f"Failed to write alert: {e}")

@app.post("/ingest")
async def ingest(request: Request):
    """
    Main endpoint: receive streaming metrics and logs, detect anomalies
    """
    try:
        payload = await request.json()
        timestamp = payload.get("timestamp")
        metrics = payload.get("metrics", {})
        logs = payload.get("logs", [])
        
        # Store metrics in buffer
        buffer.add(payload)
        
        # Step 1: Univariate anomaly detection per metric
        univariate_anomalies, vote_counts = detect_univariate_anomalies(payload)
        
        # Step 2: Log-based anomaly detection
        log_anomalies = detect_log_anomalies(logs, timestamp)
        
        # Step 3: Combine all anomalies
        all_anomalies = {**univariate_anomalies, **log_anomalies}
        
        # Step 4: Voting + alerting
        alert_anomalies = should_alert(all_anomalies, vote_counts)
        
        if alert_anomalies:
            alert_type = map_anomaly_to_alert_type(alert_anomalies)
            severity = "critical" if alert_type == "memory_leak" else "warning"
            message = generate_alert_message(alert_anomalies, payload)
            
            write_alert(timestamp, alert_type, severity, message)
        
        return {"status": "ok", "anomalies_detected": len(alert_anomalies) > 0}
    
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
