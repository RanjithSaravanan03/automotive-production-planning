"""Step 6C: test the 1130-finished-battery buffer under both supplier policies.
Save in automotive_planning/src beside baseline_14day.py. Standard library only.
Runs temporary copies; preserves original database, policy and existing reports.
"""
from contextlib import closing, redirect_stdout
from pathlib import Path
import csv
import io
import json
import shutil
import sqlite3
import tempfile

from baseline_14day import run

ROOT = Path(__file__).resolve().parents[1]
MODES = ('demand_driven_within_capacity', 'no_unscheduled_production')


def main(root=ROOT):
    policy = json.loads((root / 'config/baseline_policy.json').read_text(encoding='utf-8-sig'))
    rows = []
    for mode in MODES:
        print(f'Running supplier policy: {mode}', flush=True)
        name = 'buffer_1130_' + mode
        with tempfile.TemporaryDirectory(prefix='verify_buffer_') as directory:
            temp_root = Path(directory)
            (temp_root / 'config').mkdir()
            (temp_root / 'data/processed').mkdir(parents=True)
            scenario_policy = json.loads(json.dumps(policy))
            scenario_policy['supplier_production']['after_fixed_schedule'] = mode
            (temp_root / 'config/baseline_policy.json').write_text(json.dumps(scenario_policy, indent=2), encoding='utf-8')
            database = temp_root / 'data/processed/planning.sqlite'
            original = root / 'data/processed/planning.sqlite'
            with closing(sqlite3.connect(original.resolve().as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(database)) as destination:
                    source.backup(destination)
                    changed = destination.execute('''
                        UPDATE arcs SET lead_time_days = 16
                        WHERE from_node = 'battery-supplier_trans' AND to_node = 'battery-supplier_prod'
                          AND lead_time_days = 20
                    ''')
                    if changed.rowcount != 1:
                        raise ValueError('Expected one original 20-day battery-component route.')
                    changed = destination.execute('''
                        UPDATE initial_inventories SET opening_stock_units = 1182
                        WHERE node_id = 'zp7' AND product_id = 'BEV' AND period = 60
                          AND opening_stock_units = 52 AND max_inventory_units >= 1182
                    ''')
                    if changed.rowcount != 1:
                        raise ValueError('Expected original 52-battery opening stock and sufficient inventory limit.')
                    destination.commit()
            with redirect_stdout(io.StringIO()):
                result = run(temp_root)
            result['scenario_name'] = name
            result['limitations'] = [x for x in result['limitations'] if not x.startswith('No new 20/23-day')]
            result['limitations'].extend([
                'Hypothetical component transit of 16 days, applied to existing shipments; no new upstream departures.',
                'Hypothetical extra 1130 finished BEV batteries at zp7 before Day 61 (opening total 1182).',
                'Extra-stock source, pre-horizon capacity, procurement, carrying cost and expedited service availability are not established.',
                'A deterministic scenario sensitivity, not an economic safety-stock or cost-optimal recommendation.'
            ])
            assumptions = {'component_transit_days': 16, 'extra_finished_batteries': 1130,
                           'original_opening_stock': 52, 'scenario_opening_stock': 1182,
                           'buffer_node': 'zp7', 'buffer_available': 'before Day 61',
                           'post_day_70_policy': mode, 'new_upstream_departures': 0,
                           'existing_shipment_quantities_and_departures': 'unchanged',
                           'production_and_transport_capacities': 'unchanged',
                           'commercial_and_pre_horizon_feasibility': 'not established'}
            out = root / 'reports' / name
            shutil.copytree(temp_root / 'reports/baseline_14day', out, dirs_exist_ok=True)
            (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            (out / 'scenario_assumptions.json').write_text(json.dumps(assumptions, indent=2) + '\n', encoding='utf-8')
            keys = ('produced_units', 'unfulfilled_units', 'on_time_units', 'on_time_pct',
                    'backlog_unit_days', 'feasibility_checks')
            rows.append({'post_day_70_policy': mode, **{k: result[k] for k in keys}})
    same = all(rows[0][k] == rows[1][k] for k in rows[0] if k != 'post_day_70_policy')
    full = all(r['produced_units'] == 28000 and r['unfulfilled_units'] == 0 and
               r['on_time_units'] == 28000 and r['backlog_unit_days'] == 0 and
               r['feasibility_checks'] == 'PASS' for r in rows)
    output = root / 'reports/buffer_supplier_policy_check'
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'comparison.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    conclusion = {'identical_tested_metrics': same, 'full_on_time_fulfilment_under_both_policies': full,
                  'scope': '14-day horizon, 16-day transit, extra 1130 finished batteries before Day 61; other assumptions unchanged',
                  'commercial_feasibility': 'not established'}
    (output / 'verification.json').write_text(json.dumps(conclusion, indent=2) + '\n', encoding='utf-8')
    lines = ['STEP 6C - BUFFER SUPPLIER POLICY CHECK',
             'POLICY | PRODUCED | UNFULFILLED | ON TIME | ON-TIME % | BACKLOG UNIT-DAYS | CHECKS']
    lines += [f"{r['post_day_70_policy']} | {r['produced_units']} | {r['unfulfilled_units']} | {r['on_time_units']} | {r['on_time_pct']} | {r['backlog_unit_days']} | {r['feasibility_checks']}" for r in rows]
    lines += ['', f'Identical tested metrics: {same}', f'Full on-time fulfilment under both policies: {full}',
              'Extra stock and expedited transport are hypothetical; costs and pre-horizon availability are not established.',
              'Saved: reports/buffer_supplier_policy_check/']
    text = '\n'.join(lines) + '\n'
    (output / 'console.txt').write_text(text, encoding='utf-8')
    print('\n' + text)
    return conclusion


if __name__ == '__main__':
    main()
