from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path('.').resolve()
OUT = ROOT / 'thesis_tables'
OUT.mkdir(exist_ok=True)


def safe_read_csv(path):
    path = Path(path)
    if not path.exists():
        print(f'[skip] missing: {path}')
        return None
    return pd.read_csv(path)


def latex_escape(s):
    if pd.isna(s):
        return ''
    s = str(s)
    return (s.replace('_', '\\_')
             .replace('%', '\\%')
             .replace('&', '\\&'))


def write_table(df, out_path, caption, label, col_format=None):
    if col_format is None:
        col_format = 'l' * len(df.columns)
    lines = []
    lines.append('\\begin{table}[htbp]')
    lines.append('\\centering')
    lines.append(f'\\caption{{{caption}}}')
    lines.append(f'\\label{{{label}}}')
    lines.append(f'\\begin{{tabular}}{{{col_format}}}')
    lines.append('\\toprule')
    lines.append(' & '.join(df.columns) + ' \\\\')
    lines.append('\\midrule')
    for _, row in df.iterrows():
        vals = [latex_escape(v) for v in row.tolist()]
        lines.append(' & '.join(vals) + ' \\\\')
    lines.append('\\bottomrule')
    lines.append('\\end{tabular}')
    lines.append('\\end{table}')
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f'[ok] wrote {out_path}')


# Table 2: urban experiment comparison
urban_exps = [
    ('exp04_tightchip_baseline', 'Baseline'),
    ('exp05_osmref_iterative', 'OSM-ref iterative'),
    ('exp07_topology_aware', 'Topology-aware'),
    ('urban_exp08a_selective_acceptance', 'Selective acceptance'),
    ('urban_exp08b_shadow_refine', 'Selective + shadow')
]
rows = []
for exp, note in urban_exps:
    df = safe_read_csv(ROOT / 'outputs' / exp / 'external_eval_osm2025.csv')
    if df is None:
        continue
    rows.append({
        'Experiment': exp,
        'Mean IoU final vs OSM 2025': f"{df['iou_final_vs_osm2025'].mean():.3f}",
        'Improved objects': f"{int(df['improved_vs_2018'].sum())}/{len(df)}",
        'Note': note,
    })
if rows:
    write_table(pd.DataFrame(rows), OUT / 'tab_urban_experiment_comparison.tex',
                'Comparison of the main urban experiment variants against the retrospective OSM~2025 reference.',
                'tab:urban_experiment_comparison', 'p{4.2cm}ccc')

# Table 4: automatic routing approximation
for fname, label in [('urban_auto_features_v2.csv', 'tab:auto_routing_match')]:
    df = safe_read_csv(ROOT / 'outputs' / 'urban_phaseB' / fname)
    if df is None:
        continue
    summary = pd.DataFrame([
        {'Metric': 'Correct route matches', 'Value': int(df['route_match'].sum())},
        {'Metric': 'Incorrect route matches', 'Value': int((~df['route_match']).sum())},
        {'Metric': 'Total cases', 'Value': len(df)},
    ])
    write_table(summary, OUT / 'tab_auto_routing_match.tex',
                'Agreement between manual routing decisions and the automatically approximated routing logic.',
                label, 'lc')

# Table 5: urban change-type classification
ct = safe_read_csv(ROOT / 'outputs' / 'urban_change_types' / 'urban_change_type_report.csv')
if ct is not None:
    pred_counts = ct['predicted_change_type'].value_counts().to_dict()
    ref_counts = ct['reference_change_type'].value_counts().to_dict()
    agree = int(ct['reference_match'].sum())
    total = len(ct)
    rows = [
        {'Metric': 'Predicted unchanged', 'Value': pred_counts.get('unchanged', 0)},
        {'Metric': 'Predicted modified', 'Value': pred_counts.get('modified', 0)},
        {'Metric': 'Predicted review', 'Value': pred_counts.get('review', 0)},
        {'Metric': 'Reference unchanged', 'Value': ref_counts.get('unchanged', 0)},
        {'Metric': 'Reference modified', 'Value': ref_counts.get('modified', 0)},
        {'Metric': 'Exact agreement', 'Value': f'{agree}/{total}'},
    ]
    write_table(pd.DataFrame(rows), OUT / 'tab_urban_change_types.tex',
                'Summary of the urban change-type classification layer.',
                'tab:urban_change_types', 'lc')

# Table 1 simple dataset overview skeleton (manual fill possible)
overview = pd.DataFrame([
    {'Scenario': 'Urban Berlin', 'Historical OSM': '2018', 'Current imagery': 'Orthophoto 2025', 'Evaluation reference': 'OSM 2025'},
    {'Scenario': 'Rural Lübars', 'Historical OSM': '2018', 'Current imagery': 'Orthophoto 2025', 'Evaluation reference': 'OSM 2025'},
])
write_table(overview, OUT / 'tab_dataset_overview.tex',
            'Overview of the two main study scenarios and their temporal setup.',
            'tab:dataset_overview', 'p{3cm}ccc')

# Table 3 rural status summary skeleton
rural = pd.DataFrame([
    {'Status': 'unchanged', 'Main finding': 'Best handled by conservative keep-biased verification'},
    {'Status': 'changed', 'Main finding': 'Improved by larger context, relaxed prompting, and re-ranking'},
    {'Status': 'removed', 'Main finding': 'Behaved as a relatively stable special case'},
    {'Status': 'new', 'Main finding': 'Possible under favourable visibility, harder for small or occluded buildings'},
])
write_table(rural, OUT / 'tab_rural_status_summary.tex',
            'Condensed status-wise summary of the rural findings.',
            'tab:rural_status_summary', 'lp{10cm}')
