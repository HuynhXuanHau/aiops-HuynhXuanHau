# Process for Evidence-Driven Remediation Lab

This document records the steps I will follow to implement the lab and the order of work.

## 1. Review inputs and requirements

- Read `HANDOUT.md` carefully.
- Inspect `eval/E01.json` and several other eval incidents to understand the incident schema.
- Inspect `incidents_history.json` to understand the historical representation.
- Inspect `actions.yaml` and `eval/expected.json` to know the allowed actions and grading criteria.
- Note schema pitfalls from the handout (§2.6).

## 2. Define repository structure

Target files:
- `engine.py` — CLI entry point and audit writer.
- `features.py` — Layer 1: feature extraction from raw incident evidence.
- `retrieval.py` — Layer 2: similarity, neighbor search, and outcome-weighted voting.
- `decision.py` — Layer 3: cost-aware action selection and escalation logic.
- `audit.jsonl` — output for all eval incidents.
- `FINDINGS.md` — lab reflection answers.
- `README.md` — usage instructions.

## 3. Implement the CLI and wiring first

- Write `engine.py` with `decide --incident --history --actions`.
- Wire the three layers together with placeholder functions.
- Confirm the CLI runs end-to-end with a stub decision output.

## 4. Implement Layer 1: incident representation

- Parse raw logs into stable templates or clusters.
- Extract trace anomaly signals (`error_rate`, `p99 ratio`, affected edges).
- Derive affected services from `trigger_alert`, anomalous trace edges, and log bursts.
- Build a hybrid incident vector that includes both log and trace signals.

## 5. Implement Layer 2: retrieval and voting

- Parse historical `actions_taken` strings into structured candidates.
- Compute similarity between new incident and each history entry.
- Use a combined log+trace distance.
- Weight history neighbours by outcome: success > partial > failed.
- Produce a candidate action list with confidence scores.

## 6. Implement Layer 3: decision logic

- Load `actions.yaml` metadata.
- Score candidate actions with expected value, cost, and blast radius.
- Apply a safety gate for `page_oncall` and low-confidence cases.
- Return final selected action plus audit evidence.

## 7. Run eval incidents and collect audit log

- Run the engine for `E01` through `E08`.
- Save one line per incident in `audit.jsonl`.
- Compare results against `eval/expected.json`.
- Result: engine produced 8/8 correct according to `grade.py`.

## 8. Write findings and finalize

- Record the actual similarity function and why it was chosen.
- Explain how outcome-weighted voting changed rankings.
- Document one full expected-value calculation.
- Note when `page_oncall` was chosen and whether it matched ground truth.
- Identify the likely failure mode and a concrete improvement.

## 9. Optional verification

- If time permits, implement OOD detection and detailed `evidence` chains.
- If possible, run `grade.py --audit audit.jsonl --expected eval/expected.json`.
