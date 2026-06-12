import argparse
import json
from pathlib import Path

from features import extract_features
from retrieval import retrieve_and_vote
from decision import select_action


def decide(incident_path: Path, history_path: Path, actions_path: Path) -> dict:
    incident = json.loads(incident_path.read_text())
    history = json.loads(history_path.read_text())
    actions_catalog = json.loads(actions_path.read_text()) if actions_path.suffix == ".json" else None

    # If actions.yaml is provided, load with pyyaml.
    if actions_catalog is None:
        import yaml

        actions_catalog = yaml.safe_load(actions_path.read_text())

    features = extract_features(incident)
    candidates = retrieve_and_vote(features, history)
    decision = select_action(candidates, actions_catalog)
    decision["incident_id"] = incident_path.stem
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-driven remediation engine")
    subparsers = parser.add_subparsers(dest="cmd")

    decide_parser = subparsers.add_parser("decide", help="Decide on a remediation action")
    decide_parser.add_argument("--incident", required=True, help="Path to incident JSON")
    decide_parser.add_argument("--history", default="incidents_history.json", help="Path to history JSON")
    decide_parser.add_argument("--actions", default="actions.yaml", help="Path to actions catalog YAML")

    args = parser.parse_args()
    if args.cmd != "decide":
        parser.print_help()
        return 1

    result = decide(Path(args.incident), Path(args.history), Path(args.actions))
    print(json.dumps(result, indent=2))
    with open("audit.jsonl", "a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
