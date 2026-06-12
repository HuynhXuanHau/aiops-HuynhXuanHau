import re
from collections import Counter
from statistics import median
from typing import Any

NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
PATH_RE = re.compile(r"\b[a-zA-Z0-9_/.-]+\.(?:js|py|java|go|yaml|yml|json|properties|proto|conf)\b")


def normalize_log_template(msg: str) -> str:
    msg = msg.lower()
    msg = UUID_RE.sub("<ID>", msg)
    msg = HEX_RE.sub("<HEX>", msg)
    msg = PATH_RE.sub("<PATH>", msg)
    msg = NUM_RE.sub("<NUM>", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg


def build_log_signatures(logs: list[dict]) -> list[str]:
    normalized = []
    for entry in logs:
        template = normalize_log_template(entry.get("msg", ""))
        if template:
            normalized.append(template)
    counts = Counter(normalized)
    return [sig for sig, _ in counts.most_common(30)]


def group_traces(traces: list[dict]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for trace in traces:
        edge = (trace.get("from"), trace.get("to"))
        if edge not in groups:
            groups[edge] = {
                "counts": [],
                "error_counts": [],
                "p99s": [],
                "total_count": 0,
                "total_errors": 0,
            }
        g = groups[edge]
        cnt = trace.get("count", 0) or 0
        err = trace.get("error_count", 0) or 0
        p99 = trace.get("p99_ms", 0) or 0
        g["counts"].append(cnt)
        g["error_counts"].append(err)
        g["p99s"].append(p99)
        g["total_count"] += cnt
        g["total_errors"] += err
    for g in groups.values():
        g["error_rate"] = g["total_errors"] / g["total_count"] if g["total_count"] else 0.0
        if g["p99s"]:
            g["p99_median"] = median(g["p99s"])
            g["p99_max"] = max(g["p99s"])
            g["p99_ratio"] = (g["p99_max"] / g["p99_median"]) if g["p99_median"] > 0 else 1.0
        else:
            g["p99_median"] = 0.0
            g["p99_max"] = 0.0
            g["p99_ratio"] = 1.0
    return groups


def build_trace_signatures(trace_groups: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    signatures = []
    for (src, dst), g in trace_groups.items():
        if g["p99_ratio"] >= 1.7 or g["error_rate"] >= 0.08:
            signatures.append({
                "from": src,
                "to": dst,
                "p99_deviation_ratio": round(g["p99_ratio"], 2),
                "error_rate": round(g["error_rate"], 3),
            })
    return sorted(signatures, key=lambda s: (-s["p99_deviation_ratio"], -s["error_rate"]))


def derive_affected_services(incident: dict, trace_signatures: list[dict]) -> list[str]:
    services = set()
    trigger = incident.get("trigger_alert", {}).get("service")
    if trigger:
        services.add(trigger)
    for entry in incident.get("logs", []):
        svc = entry.get("svc")
        level = entry.get("level", "").upper()
        if svc and level in {"ERROR", "WARN"}:
            services.add(svc)
    for trace in trace_signatures:
        if trace.get("from"):
            services.add(trace["from"])
        if trace.get("to"):
            services.add(trace["to"])
    return sorted(services)


def derive_root_service(incident: dict, trace_signatures: list[dict]) -> str | None:
    weights = Counter()
    trigger = incident.get("trigger_alert", {}).get("service")
    if trigger:
        weights[trigger] += 0.5
    for entry in incident.get("logs", []):
        svc = entry.get("svc")
        level = entry.get("level", "").upper()
        if not svc:
            continue
        if level == "ERROR":
            weights[svc] += 1.4
        elif level == "WARN":
            weights[svc] += 0.8
    for trace in trace_signatures:
        src = trace.get("from")
        dst = trace.get("to")
        if src:
            weights[src] += 0.7
        if dst:
            weights[dst] += 1.3
        weights[dst] += trace.get("error_rate", 0.0) * 2.0
        weights[dst] += trace.get("p99_deviation_ratio", 1.0) * 0.5
    if not weights:
        return trigger
    return weights.most_common(1)[0][0]


def extract_features(incident: dict) -> dict[str, Any]:
    logs = incident.get("logs", [])
    traces = incident.get("traces", [])
    log_signatures = build_log_signatures(logs)
    trace_groups = group_traces(traces)
    trace_signatures = build_trace_signatures(trace_groups)
    affected_services = derive_affected_services(incident, trace_signatures)
    root_service = derive_root_service(incident, trace_signatures)
    return {
        "incident_id": incident.get("incident_id"),
        "trigger_service": incident.get("trigger_alert", {}).get("service"),
        "root_service": root_service,
        "log_signatures": log_signatures,
        "trace_signatures": trace_signatures,
        "affected_services": affected_services,
        "trace_groups": trace_groups,
    }
