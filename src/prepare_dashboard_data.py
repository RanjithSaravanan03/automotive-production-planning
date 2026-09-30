"""Step 7A: consolidate three saved scenarios for a dashboard.
Save in automotive_planning/src. Python 3.10+, no additional packages.
Reads saved reports and writes data/dashboard/. Does not rerun simulations.
Join each fact table to scenarios.csv using scenario_id. Never sum scenarios.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ('baseline', 'Baseline', 'baseline_14day', 20, 0),
    ('expedited', 'Expedited transit', 'scenario_battery_expedited', 16, 0),
    ('buffer', 'Expedited + opening battery buffer', 'buffer_1130_demand_driven_within_capacity', 16, 1130),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(root=ROOT):
    scenarios, kpis, daily_rows, capacity_rows, inventory_rows, order_rows = [], [], [], [], [], []
    inputs = {}
    for sid, label, folder, transit, extra in CASES:
        report = root / 'reports' / folder
        require(report.exists(), f'Missing {report}. Run the relevant scenario script first.')
        def read(name):
            path = report / name
            inputs[f'{folder}/{name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open(newline='', encoding='utf-8-sig') as stream:
                return list(csv.DictReader(stream))
        def read_json(name):
            path = report / name
            inputs[f'{folder}/{name}'] = hashlib.sha256(path.read_bytes()).hexdigest()
            return json.loads(path.read_text(encoding='utf-8-sig'))
        summary = read_json('summary.json')
        policy = read_json('policy_used.json')
        start, end = policy['start_period'], policy['end_period']
        require(summary['feasibility_checks'] == 'PASS', f'{sid}: simulation checks did not pass.')
        require(summary['post_day_70_policy'] == 'demand_driven_within_capacity', f'{sid}: different supplier policy.')
        if sid != 'baseline':
            assumptions = read_json('scenario_assumptions.json')
            actual_transit = assumptions.get('scenario_transit_days', assumptions.get('component_transit_days'))
            require(actual_transit == transit, f'{sid}: unexpected transit assumption.')
            if sid == 'buffer':
                require(assumptions['extra_finished_batteries'] == extra, 'Unexpected opening buffer.')
        scenarios.append({'scenario_id': sid, 'scenario_label': label, 'source_report_folder': folder,
                          'start_day': start, 'end_day': end, 'component_transit_days': transit,
                          'extra_opening_finished_batteries': extra,
                          'post_day_70_policy': summary['post_day_70_policy'],
                          'method': summary['method'], 'result_type': 'simulation',
                          'assumption_note': 'Recorded inputs and explicit baseline policies.' if sid == 'baseline' else
                              'Hypothetical 16-day transit; availability and cost unverified.' if sid == 'expedited' else
                              'Hypothetical 16-day transit plus 1130 extra finished batteries before Day 61; availability and cost unverified.'})
        daily = read('daily_summary.csv')
        caps = read('capacity_ledger.csv')
        inventory = read('inventory_ledger.csv')
        orders = read('order_results.csv')
        require([int(r['period']) for r in daily] == list(range(start, end + 1)), f'{sid}: incomplete daily horizon.')
        assembly = {int(r['period']): r for r in caps if r['from_node'] == 'zp7' and r['to_node'] == 'zp8'}
        status_counts = Counter(r['status'] for r in orders)
        require(status_counts['unfulfilled'] == summary['unfulfilled_units'], f'{sid}: unfulfilled mismatch.')
        require(status_counts['on_time'] == summary['on_time_units'], f'{sid}: on-time mismatch.')
        require(status_counts['late'] == summary['late_completed_units'], f'{sid}: late mismatch.')
        require(len(orders) == summary['demand_units'], f'{sid}: demand mismatch.')
        require(sum(int(r['produced_today']) for r in daily) == summary['produced_units'], f'{sid}: production mismatch.')
        require(sum(int(r['backlog_end_of_day']) for r in daily) == summary['backlog_unit_days'], f'{sid}: backlog-days mismatch.')
        require(int(daily[-1]['backlog_end_of_day']) == summary['unfulfilled_units'], f'{sid}: terminal backlog mismatch.')
        total_capacity = sum(int(r['capacity_units']) for r in assembly.values())
        row = {'scenario_id': sid, **{k: summary[k] for k in (
            'demand_units', 'produced_units', 'unfulfilled_units', 'on_time_units', 'late_completed_units',
            'horizon_fulfilment_pct', 'on_time_pct', 'backlog_unit_days', 'feasibility_checks')},
            'assembly_capacity_units': total_capacity,
            'assembly_utilization_pct': round(100 * summary['produced_units'] / total_capacity, 2)}
        kpis.append(row)
        for r in daily:
            day, made = int(r['period']), int(r['produced_today'])
            c = assembly[day]
            require(int(c['used_units']) == made, f'{sid}: assembly capacity ledger mismatch on Day {day}.')
            daily_rows.append({'scenario_id': sid, **{k: int(r[k]) for k in (
                'period', 'due_today', 'produced_today', 'cumulative_produced', 'backlog_end_of_day')},
                'assembly_capacity_units': int(c['capacity_units']),
                'unused_assembly_slots': int(c['capacity_units']) - made,
                'assembly_utilization_pct': float(r['assembly_utilization_pct'])})
        for r in caps:
            capacity_rows.append({'scenario_id': sid, 'period': int(r['period']),
                                  'from_node': r['from_node'], 'to_node': r['to_node'],
                                  'route': r['from_node'] + ' -> ' + r['to_node'],
                                  'capacity_units': int(r['capacity_units']), 'used_units': int(r['used_units']),
                                  'unused_units': int(r['capacity_units']) - int(r['used_units']),
                                  'utilization_pct': float(r['utilization_pct']) if r['utilization_pct'] else None})
        for r in inventory:
            nums = {k: int(r[k]) for k in ('opening_units', 'receipts_units', 'consumed_or_dispatched_units', 'closing_units')}
            require(nums['opening_units'] + nums['receipts_units'] - nums['consumed_or_dispatched_units'] == nums['closing_units'],
                    f'{sid}: inventory roll-forward mismatch.')
            inventory_rows.append({'scenario_id': sid, 'period': int(r['period']),
                                   'node_id': r['node_id'], 'product_id': r['product_id'], **nums})
        counts = Counter((int(r['due_period']), int(r['completion_period']) if r['completion_period'] else None,
                          r['status'], int(r['delay_days_if_completed']) if r['delay_days_if_completed'] else None,
                          r['last_observed_blocker']) for r in orders)
        for (due, completion, status, delay, blocker), count in counts.items():
            order_rows.append({'scenario_id': sid, 'due_period': due, 'completion_period': completion,
                               'status': status, 'delay_days_if_completed': delay,
                               'last_observed_blocker': blocker, 'order_units': count})
    baseline = kpis[0]
    for r in kpis:
        r['additional_completed_vs_baseline'] = r['produced_units'] - baseline['produced_units']
        r['additional_on_time_vs_baseline'] = r['on_time_units'] - baseline['on_time_units']
        r['on_time_improvement_pp_vs_baseline'] = round(100 * (r['on_time_units'] / r['demand_units'] -
                                                          baseline['on_time_units'] / baseline['demand_units']), 2)
        r['backlog_unit_days_reduction_vs_baseline'] = baseline['backlog_unit_days'] - r['backlog_unit_days']
    output = root / 'data/dashboard'
    output.mkdir(parents=True, exist_ok=True)
    tables = {'scenarios.csv': scenarios, 'kpi_summary.csv': kpis, 'daily_performance.csv': daily_rows,
              'capacity_utilization.csv': capacity_rows, 'inventory_positions.csv': inventory_rows,
              'order_outcomes.csv': order_rows}
    for name, rows in tables.items():
        write_csv(output / name, rows, list(rows[0]))
    manifest = {'export_checks': 'PASS', 'scenario_count': len(scenarios),
                'table_row_counts': {name: len(rows) for name, rows in tables.items()},
                'input_sha256': inputs,
                'dashboard_rules': ['Filter by one scenario for KPI cards; compare scenarios by label.',
                                    'Join each fact table to scenarios.csv on scenario_id with one-to-many relationships.',
                                    'Never sum demand or completed units across alternative scenarios.',
                                    'Inventory and backlog are snapshots: use the selected day, not a sum over days.',
                                    'Sum daily closing backlog only for the specifically labelled backlog unit-days metric.',
                                    'Compute utilization as SUM(used_units)/SUM(capacity_units); use a consistent route and unit.',
                                    'on_time_pct uses all demand as denominator; on_time_improvement_pp is percentage points.',
                                    'order_outcomes is aggregated: sum order_units, do not count its rows.',
                                    'Order blockers are last-observed checks, not independent root-cause attribution.',
                                    'Keep the hypothetical scenario notes visible; no economic or actual service claim.']}
    (output / 'export_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('STEP 7A - DASHBOARD DATA EXPORT')
    for r in kpis:
        print(f"{r['scenario_id']} | produced={r['produced_units']} | unfulfilled={r['unfulfilled_units']} | on_time={r['on_time_pct']}% | backlog_unit_days={r['backlog_unit_days']}")
    print('\nExport checks: PASS')
    for name, rows in tables.items():
        print(f'{name}: {len(rows)} rows')
    print('Saved: data/dashboard/')
    print('KPI cards must select one scenario. Read export_manifest.json for aggregation rules.')


if __name__ == '__main__':
    main()
