from collections import defaultdict
from typing import Any

from features import normalize_log_template

OUTCOME_WEIGHT = {
    "success": 1.0,
    "partial": 0.6,
    "failed": 0.1,
}

SERVICE_ACTIONS = {"rollback_service", "increase_pool_size", "restart_pod"}


def parse_history_action(action_text: str) -> dict[str, Any]:
    parts = action_text.split(":")
    name = parts[0]
    params = parts[1:]
    if name == "rollback_service":
        return {"name": name, "params": {"service": params[0] if params else "unknown", "target_version": params[1] if len(params) > 1 else "previous"}}
    if name == "increase_pool_size":
        return {"name": name, "params": {"service": params[0] if params else "unknown", "from_value": params[1] if len(params) > 1 else "?", "to_value": params[2] if len(params) > 2 else "?"}}
    if name == "restart_pod":
        return {"name": name, "params": {"service": params[0] if params else "unknown", "pod_selector": params[1] if len(params) > 1 else "default"}}
    if name == "dns_config_rollback":
        return {"name": name, "params": {"configmap_name": params[0] if params else "unknown", "target_revision": params[1] if len(params) > 1 else "previous"}}
    if name == "network_policy_revert":
        return {"name": name, "params": {"policy_name": params[0] if params else "unknown"}}
    if name == "page_oncall":
        return {"name": name, "params": {"team": params[0] if params else "platform-team"}}
    return {"name": name, "params": {f"param{i}": v for i, v in enumerate(params, start=1)}}


def log_template_match(query_templates: list[str], hist_signature: str) -> bool:
    hist_norm = normalize_log_template(hist_signature)
    if hist_norm in query_templates:
        return True
    for q in query_templates:
        if hist_norm in q or q in hist_norm:
            return True
        q_tokens = set(q.split())
        h_tokens = set(hist_norm.split())
        if q_tokens and h_tokens and len(q_tokens & h_tokens) / max(len(q_tokens), len(h_tokens)) >= 0.6:
            return True
    return False


def trace_signature_similarity(query_traces: list[dict], history_traces: list[dict]) -> float:
    if not history_traces and not query_traces:
        return 1.0
    if not history_traces:
        return 0.35
    if not query_traces:
        return 0.0
    matched = 0
    for h in history_traces:
        for q in query_traces:
            if q["from"] == h["from"] and q["to"] == h["to"]:
                if q["p99_deviation_ratio"] >= h["p99_deviation_ratio"] * 0.75 or q["error_rate"] >= h["error_rate"] * 0.75:
                    matched += 1
                    break
    return matched / len(history_traces)


def affected_service_similarity(query_services: list[str], history_services: list[str]) -> float:
    if not query_services or not history_services:
        return 0.0
    qset = set(query_services)
    hset = set(history_services)
    shared = qset & hset
    union = qset | hset
    return len(shared) / len(union)


def score_history_entry(query: dict, history_entry: dict) -> float:
    query_logs = query.get("log_signatures", [])
    history_logs = history_entry.get("log_signatures", [])
    history_trace = history_entry.get("trace_signatures", [])
    query_trace = query.get("trace_signatures", [])
    log_matches = 0
    for hist_sig in history_logs:
        if log_template_match(query_logs, hist_sig):
            log_matches += 1
    log_score = log_matches / len(history_logs) if history_logs else 0.0
    trace_score = trace_signature_similarity(query_trace, history_trace)
    service_score = affected_service_similarity(query.get("affected_services", []), history_entry.get("affected_services", []))
    if not history_trace:
        log_weight, trace_weight, service_weight = 0.55, 0.15, 0.3
    else:
        log_weight, trace_weight, service_weight = 0.45, 0.35, 0.2
    return log_score * log_weight + trace_score * trace_weight + service_score * service_weight


def candidate_key(action: dict) -> tuple[str, str]:
    name = action["name"]
    if name in SERVICE_ACTIONS:
        return (name, action["params"].get("service", "unknown"))
    return (name, "")


def format_candidate(action: dict) -> dict[str, Any]:
    return {"name": action["name"], "params": action["params"]}


def retrieve_and_vote(query: dict, history: list[dict], top_k: int = 3) -> dict[str, Any]:
    candidate_scores: dict[tuple[str, str], float] = defaultdict(float)
    candidate_details: dict[tuple[str, str], dict[str, Any]] = {}
    neighbor_rows = []
    total_similarity = 0.0

    root_service = query.get("root_service")
    for entry in history:
        similarity = score_history_entry(query, entry)
        outcome = OUTCOME_WEIGHT.get(entry.get("outcome", "partial"), 0.6)
        vote_strength = similarity * outcome
        if vote_strength <= 0:
            continue
        total_similarity += vote_strength
        history_actions = entry.get("actions_taken", [])
        for action_text in history_actions:
            action = parse_history_action(action_text)
            key = candidate_key(action)
            candidate_scores[key] += vote_strength
            if key not in candidate_details:
                candidate_details[key] = {
                    "action": action,
                    "support": 0,
                    "score": 0.0,
                    "service_alignment": 0.0,
                }
            candidate_details[key]["support"] += 1
            candidate_details[key]["score"] += vote_strength
            if action["name"] in SERVICE_ACTIONS:
                service = action["params"].get("service")
                if service in query.get("affected_services", []):
                    candidate_details[key]["service_alignment"] += 0.05 * vote_strength
                elif root_service and root_service != service and root_service in query.get("affected_services", []):
                    adjusted_action = {
                        "name": action["name"],
                        "params": {**action["params"], "service": root_service},
                    }
                    adjusted_key = candidate_key(adjusted_action)
                    adjusted_score = vote_strength * 0.9
                    if adjusted_key not in candidate_details:
                        candidate_details[adjusted_key] = {
                            "action": adjusted_action,
                            "support": 0,
                            "score": 0.0,
                            "service_alignment": 0.0,
                        }
                    candidate_details[adjusted_key]["support"] += 1
                    candidate_details[adjusted_key]["score"] += adjusted_score
                    candidate_details[adjusted_key]["service_alignment"] += 0.1 * vote_strength
        neighbor_rows.append({
            "id": entry.get("id"),
            "similarity": round(similarity, 3),
            "outcome": entry.get("outcome"),
            "actions": entry.get("actions_taken", []),
        })

    for key, detail in candidate_details.items():
        detail["score"] = round(detail["score"] + detail["service_alignment"], 4)

    sorted_keys = sorted(candidate_details.keys(), key=lambda k: (-candidate_details[k]["score"], candidate_details[k]["support"]))
    candidates = []
    total_raw = sum(detail["score"] for detail in candidate_details.values())
    for key in sorted_keys:
        detail = candidate_details[key]
        candidates.append({
            "selected_action": detail["action"]["name"],
            "params": detail["action"]["params"],
            "score": round(detail["score"], 4),
            "support": detail["support"],
        })

    neighbors = sorted(neighbor_rows, key=lambda x: (-x["similarity"], x["outcome"]))[:top_k]
    consensus_score = 0.0
    if total_raw > 0:
        consensus_score = candidates[0]["score"] / total_raw

    return {
        "candidates": candidates,
        "top_3_neighbors": neighbors,
        "history_matches": neighbors,
        "raw_total_similarity": round(total_similarity, 4),
        "consensus_score": round(consensus_score, 4),
    }
