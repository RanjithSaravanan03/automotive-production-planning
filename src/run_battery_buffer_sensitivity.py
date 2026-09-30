"""Step 6B: hypothetical Day-61 finished-BEV buffer, with 16-day transit.
Save beside baseline_14day.py in src. Standard library only, Python 3.10+.
Original database, policy and reports are preserved. Runs use temporary copies.
This is a supply-availability experiment, not a procurement or safety-stock model.
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
EXTRA_BATTERIES = (0, 424, 1130)
TRANSIT_DAYS = 16
METRICS = ('produced_units', 'unfulfilled_units', 'on_time_units',
           'on_time_pct', 'backlog_unit_days', 'feasibility_checks')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main(root=ROOT):
    original_policy = json.loads((root / 'config/baseline_policy.json').read_text(encoding='utf-8-sig'))
    require(original_policy['supplier_production']['after_fixed_schedule'] == 'demand_driven_within_capacity',
            'Expected the current default supplier policy; inspect before changing it.')
    reference = json.loads((root / 'reports/scenario_battery_expedited/summary.json').read_text(encoding='utf-8-sig'))
    source_path = root / 'data/processed/planning.sqlite'
    comparison = []
    console = ['STEP 6B - FINISHED BATTERY BUFFER SENSITIVITY',
               'All cases use 16-day component transit and unchanged capacities.',
               'Extra finished BEV batteries are available at zp7 BEFORE Day 61.']
    for extra in EXTRA_BATTERIES:
        name = f'scenario_battery_buffer_{extra}'
        print(f'Running {name} ...', flush=True)
        with tempfile.TemporaryDirectory(prefix='battery_buffer_') as directory:
            scenario_root = Path(directory)
            (scenario_root / 'config').mkdir()
            (scenario_root / 'data/processed').mkdir(parents=True)
            shutil.copy2(root / 'config/baseline_policy.json', scenario_root / 'config/baseline_policy.json')
            destination_path = scenario_root / 'data/processed/planning.sqlite'
            with closing(sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(destination_path)) as destination:
                    source.backup(destination)
                    route = destination.execute('''
                        UPDATE arcs SET lead_time_days = ?
                        WHERE from_node = 'battery-supplier_trans'
                          AND to_node = 'battery-supplier_prod'
                          AND lead_time_days = 20
                    ''', (TRANSIT_DAYS,))
                    require(route.rowcount == 1, 'Expected exactly one original 20-day battery-component route.')
                    opening = destination.execute('''
                        SELECT opening_stock_units, max_inventory_units FROM initial_inventories
                        WHERE node_id = 'zp7' AND product_id = 'BEV' AND period = 60
                    ''').fetchall()
                    require(len(opening) == 1, 'Expected one BEV opening record at zp7, period 60.')
                    opening_before, inventory_limit = opening[0]
                    require(opening_before == 52, 'Opening BEV stock differs from the audited dataset.')
                    require(opening_before + extra <= inventory_limit, 'Buffer exceeds recorded inventory limit.')
                    destination.execute('''
                        UPDATE initial_inventories SET opening_stock_units = opening_stock_units + ?
                        WHERE node_id = 'zp7' AND product_id = 'BEV' AND period = 60
                    ''', (extra,))
                    destination.commit()
            with redirect_stdout(io.StringIO()):
                result = run(scenario_root)
            if extra == 0:
                require(all(result[key] == reference[key] for key in METRICS),
                        'Zero-buffer control differs from the saved expedited scenario. Stop and inspect inputs.')
            result['scenario_name'] = name
            result['extra_finished_batteries_at_zp7_before_day_61'] = extra
            result['limitations'] = [x for x in result['limitations'] if not x.startswith('No new 20/23-day')]
            result['limitations'].extend([
                'Hypothetical 16-day component transit applied to existing shipments; no new upstream departures.',
                f'Hypothetical additional {extra} finished BEV batteries at assembly before Day 61.',
                'Source, pre-horizon production/transport capacity, procurement cost and carrying cost of extra stock are not established.',
                'This buffer is additional supply; it is not a simulation of expediting the Day-60 component shipment.',
                'The existing heuristic is reused. No optimal service or economic safety-stock claim.'
            ])
            assumptions = {
                'component_transit_days': TRANSIT_DAYS,
                'extra_finished_batteries': extra,
                'buffer_location': 'zp7', 'buffer_available': 'before Day 61',
                'original_opening_batteries': opening_before,
                'scenario_opening_batteries': opening_before + extra,
                'existing_shipment_quantities_and_departures': 'unchanged',
                'production_and_transport_capacities': 'unchanged',
                'new_upstream_departures': 0,
                'post_day_70_policy': result['post_day_70_policy'],
                'buffer_feasibility_and_cost': 'not established; hypothetical sensitivity only'
            }
            output = root / 'reports' / name
            shutil.copytree(scenario_root / 'reports/baseline_14day', output, dirs_exist_ok=True)
            (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            (output / 'scenario_assumptions.json').write_text(json.dumps(assumptions, indent=2) + '\n', encoding='utf-8')
            row = {'extra_finished_batteries': extra, **{k: result[k] for k in METRICS}}
            comparison.append(row)
            console.append(f"{extra} | {result['produced_units']} | {result['unfulfilled_units']} | {result['on_time_units']} | {result['on_time_pct']} | {result['backlog_unit_days']} | {result['feasibility_checks']}")
            print(f"Completed: {result['produced_units']} cars; unfulfilled: {result['unfulfilled_units']}; checks: {result['feasibility_checks']}", flush=True)
    output = root / 'reports/battery_buffer_sensitivity'
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'comparison.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    console.insert(3, 'EXTRA BATTERIES | PRODUCED | UNFULFILLED | ON TIME | ON-TIME % | BACKLOG UNIT-DAYS | CHECKS')
    console.extend(['', 'Zero-buffer control matches the saved expedited metrics.',
                    'PASS covers in-horizon simulation checks; it does not validate procurement or pre-horizon buffer availability.',
                    'Saved: reports/battery_buffer_sensitivity/comparison.csv',
                    'Detailed ledgers: reports/scenario_battery_buffer_0, _424 and _1130/'])
    text = '\n'.join(console) + '\n'
    (output / 'console.txt').write_text(text, encoding='utf-8')
    print('\n' + text)
    return comparison


if __name__ == '__main__':
    main()
