import sqlite3, json
from pathlib import Path
import pandas as pd
import networkx as nx
import numpy as np
from collections import defaultdict

DB = Path('workshop.db')
conn = sqlite3.connect(DB)

def rrf(rankings, weights, k=60):
    score = defaultdict(float)
    for r, w in zip(rankings, weights):
        for i, svc in enumerate(r):
            score[svc] += w / (k + i + 1)
    return sorted(score.items(), key=lambda kv: -kv[1])

alerts_s07 = pd.read_sql("SELECT opened_at, severity, service, rule_id, phase FROM alerts WHERE scenario = 'S07' ORDER BY opened_at", conn)
alerts_s07['opened_at'] = pd.to_datetime(alerts_s07['opened_at'])
print('Alerts (S07):')
print(alerts_s07.to_string(index=False))

affected_s07 = set(alerts_s07['service'])
edges = pd.read_sql('SELECT src_service, dst_service FROM topology', conn)
G = nx.DiGraph()
for _, r in edges.iterrows():
    G.add_edge(r['src_service'], r['dst_service'])
sub_nodes = set(affected_s07)
for s in affected_s07:
    sub_nodes.update(G.predecessors(s))
    sub_nodes.update(G.successors(s))
sub_s07 = G.subgraph(sub_nodes)
print('\nSubgraph nodes (S07):', list(sub_s07.nodes()))
print('Subgraph edges (S07):', list(sub_s07.edges()))

Gr_s07 = sub_s07.reverse()
pers = {n: 1.0 for n in Gr_s07.nodes()}
for s in affected_s07: pers[s] = 10.0
pr_s07 = nx.pagerank(Gr_s07, personalization=pers, max_iter=100)
print('\nR1 PageRank (top5):')
for s, v in sorted(pr_s07.items(), key=lambda kv: -kv[1])[:5]:
    print(f'  {s:30s} {v:.6f}')

metrics_s07 = pd.read_sql("SELECT timestamp, service, metric, value FROM metrics WHERE scenario = 'S07' ORDER BY timestamp", conn)
earliest_s07 = {}
for (svc, m), g in metrics_s07.groupby(['service', 'metric']):
    vals = g['value'].values
    if len(vals) < 70:
        continue
    mu, sigma = vals[:60].mean(), max(vals[:60].std(), 1e-6)
    drift_idx = np.where(np.abs(vals[60:] - mu) > 3 * sigma)[0]
    if len(drift_idx) == 0:
        continue
    ts = g.iloc[60 + drift_idx[0]]['timestamp']
    if svc not in earliest_s07 or ts < earliest_s07[svc]:
        earliest_s07[svc] = ts
print('\nR2 Earliest-drift (sorted):')
for s, ts in sorted(earliest_s07.items(), key=lambda kv: kv[1]):
    print(f'  {s:30s} first drift @ {ts}')

r3_cnt = defaultdict(int)
for (svc, m), g in metrics_s07.groupby(['service', 'metric']):
    vals = g['value'].values
    if len(vals) < 70:
        continue
    mu, sigma = vals[:60].mean(), max(vals[:60].std(), 1e-6)
    if max(np.abs(vals[60:] - mu)) > 3 * sigma:
        r3_cnt[svc] += 1
print('\nR3 Drift-count (top):')
for s, c in sorted(r3_cnt.items(), key=lambda kv: -kv[1]):
    print(f'  {s:30s} {c}')

r1_s07 = [s for s, _ in sorted(pr_s07.items(), key=lambda kv: -kv[1])]
r2_s07 = [s for s, _ in sorted(earliest_s07.items(), key=lambda kv: kv[1])]
r3_s07 = [s for s, _ in sorted(r3_cnt.items(), key=lambda kv: -kv[1])]
print('\nTop list lengths:', len(r1_s07), len(r2_s07), len(r3_s07))

fused_s07 = rrf([r1_s07, r2_s07, r3_s07], [0.3, 0.5, 0.2])
print('\n=== Fused (S07) root-cause ranking ===')
for s, v in fused_s07[:10]:
    print(f'  {s:30s} {v:.6f}')

sc_s07 = json.loads(conn.execute("SELECT full_json FROM scenarios WHERE id='S07'").fetchone()[0])
expected_s07 = sc_s07['expected_rca']
fused_top = fused_s07[0][0] if fused_s07 else None
print(f"\nExpected root (S07): {expected_s07['top_service']}")
print(f"Fused #1:           {fused_top}")
print(f"Match: {fused_top == expected_s07['top_service']}")

print('\nRanker agreement with expected:')
print('  PageRank top == expected:', r1_s07[0] == expected_s07['top_service'] if r1_s07 else False)
print('  Earliest-drift top == expected:', r2_s07[0] == expected_s07['top_service'] if r2_s07 else False)
print('  Drift-count top == expected:', r3_s07[0] == expected_s07['top_service'] if r3_s07 else False)
