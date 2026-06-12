from typing import Any


def build_action_map(actions_catalog: list[dict]) -> dict[str, dict[str, Any]]:
    return {action["name"]: action for action in actions_catalog}


def select_action(candidates: dict, actions_catalog: list[dict]) -> dict[str, Any]:
    action_map = build_action_map(actions_catalog)
    candidate_list = candidates.get("candidates", [])
    if not candidate_list:
        return {
            "selected_action": "page_oncall",
            "params": {"team": "platform-team"},
            "confidence": 0.15,
            "top_3_neighbors": candidates.get("top_3_neighbors", []),
            "consensus_score": candidates.get("consensus_score", 0.0),
            "selected_action_meta": {"blast_radius_services": 0, "cost_min": 0},
            "evidence": {
                "reason": "no candidate actions from history",
                "consensus_score": candidates.get("consensus_score", 0.0),
            },
        }

    total_score = sum(c["score"] for c in candidate_list) or 1.0
    for c in candidate_list:
        normalized = c["score"] / total_score
        c["normalized_score"] = round(normalized, 4)
        c["p_success"] = round(0.2 + 0.7 * normalized, 4)
        meta = action_map.get(c["selected_action"], {})
        c["meta"] = meta
        c["cost_min"] = meta.get("cost_min", 10)
        c["blast_radius_services"] = meta.get("blast_radius_services", 0)
        c["utility"] = round(c["p_success"] - 0.04 * c["cost_min"] - 0.07 * c["blast_radius_services"], 4)

    page_candidate = next((c for c in candidate_list if c["selected_action"] == "page_oncall"), None)
    top = candidate_list[0]
    if top["selected_action"] == "page_oncall":
        confidence = max(top.get("p_success", 0.1), 0.2)
        return {
            "selected_action": "page_oncall",
            "params": top.get("params", {"team": "platform-team"}),
            "confidence": round(confidence, 3),
            "top_3_neighbors": candidates.get("top_3_neighbors", []),
            "consensus_score": candidates.get("consensus_score", 0.0),
            "selected_action_meta": {
                "blast_radius_services": top.get("blast_radius_services", 0),
                "cost_min": top.get("cost_min", 0),
            },
            "evidence": {
                "reason": "page_oncall was the highest consensus candidate",
                "top_candidate": top,
                "consensus_score": candidates.get("consensus_score", 0.0),
                "top_3_neighbors": candidates.get("top_3_neighbors", []),
            },
        }

    selected = top
    if selected["normalized_score"] < 0.18:
        if page_candidate:
            selected = page_candidate
        else:
            selected = top

    if selected["selected_action"] != "page_oncall":
        if selected["utility"] <= 0.0 and page_candidate is not None:
            selected = page_candidate
        elif selected["blast_radius_services"] > 1 and selected["p_success"] < 0.55:
            if page_candidate is not None:
                selected = page_candidate

    confidence = round(selected.get("p_success", 0.2) if selected["selected_action"] != "page_oncall" else 0.25, 3)
    if selected["selected_action"] == "page_oncall" and selected.get("params") is None:
        selected["params"] = {"team": "platform-team"}

    return {
        "selected_action": selected["selected_action"],
        "params": selected.get("params", {"team": "platform-team"}),
        "confidence": confidence,
        "top_3_neighbors": candidates.get("top_3_neighbors", []),
        "consensus_score": candidates.get("consensus_score", 0.0),
        "selected_action_meta": {
            "blast_radius_services": selected.get("blast_radius_services", 0),
            "cost_min": selected.get("cost_min", 0),
        },
        "evidence": {
            "reason": "utility and consensus based selection",
            "selected": selected,
            "top_3_neighbors": candidates.get("top_3_neighbors", []),
            "consensus_score": candidates.get("consensus_score", 0.0),
            "candidate_list": candidate_list,
        },
    }
