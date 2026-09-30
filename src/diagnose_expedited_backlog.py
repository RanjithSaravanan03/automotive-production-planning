"""Step 6A: audit saved expedited reports; Python 3.10+, standard library only.
Save in automotive_planning/src and run from the project folder.
Reads the database in read-only mode. Writes only reports/diagnosis_expedited/.
Does not rerun or change the simulation, database, policy, or existing reports.
"""
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
import csv
import hashlib
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(root=ROOT):
    reports = root / 'reports/scenario_battery_expedited'
    database = root / 'data/processed/planning.sqlite'
    require(database.exists(), f'Missing database: {database}')

    def read(name):
        with (reports / name).open(newline='', encoding='utf-8-sig') as stream:
            return list(csv.DictReader(stream))

    daily = read('daily_summary.csv')
    orders = read('order_results.csv')
    inventory = read('inventory_ledger.csv')
    capacity = read('capacity_ledger.csv')
    flows = read('new_flows.csv')
    pipeline = read('terminal_pipeline.csv')
    summary = json.loads((reports / 'summary.json').read_text(encoding='utf-8-sig'))
    policy = json.loads((reports / 'policy_used.json').read_text(encoding='utf-8-sig'))
    assumptions = json.loads((reports / 'scenario_assumptions.json').read_text(encoding='utf-8-sig'))
    start, end = policy['start_period'], policy['end_period']
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        groups = {r['product_id']: r['product_group'] for r in db.execute('SELECT * FROM products')}
        bom = defaultdict(list)
        # Match the simulation: remove identity rows from BOM.
        for r in db.execute('SELECT * FROM BOM WHERE parent_product_id != component_product_id'):
            bom[r['parent_product_id']].append((r['component_product_id'], r['component_quantity']))
        demand = {r['product_id']: dict(r) for r in db.execute('SELECT * FROM demands')}
        initial = [dict(r) for r in db.execute('SELECT * FROM initial_inventories')]
        existing = [dict(r) for r in db.execute('SELECT * FROM initial_flows')]
        lead = {(r['from_node'], r['to_node']): r['lead_time_days'] for r in db.execute('SELECT * FROM arcs')}

    upstream = ('battery-supplier_trans', 'battery-supplier_prod')
    production = ('battery-supplier_prod', 'battery-supplier_inv')
    transport = ('battery-supplier_inv', 'zp7')
    require(assumptions['changed_route'] == ' -> '.join(upstream), 'Unexpected changed route.')
    lead[upstream] = int(assumptions['scenario_transit_days'])
    require(not any((r['from_node'], r['to_node']) == upstream for r in flows),
            'This audit expects no new upstream battery-component departures.')
    require(set(demand) == {r['order_product_id'] for r in orders}, 'Order IDs differ from database.')
    require(all(demand[r['order_product_id']]['period'] == int(r['due_period']) for r in orders),
            'Saved due dates differ from database.')
    require(all(r['demand_units'] == 1 for r in demand.values()), 'Expected unit car orders.')
    unfulfilled = [r for r in orders if r['status'] == 'unfulfilled']
    require(len(unfulfilled) == summary['unfulfilled_units'], 'Summary/order count mismatch.')
    require(len(orders) - len(unfulfilled) == summary['produced_units'], 'Completed count mismatch.')
    require(sum(int(r['produced_today']) for r in daily) == summary['produced_units'], 'Daily count mismatch.')
    require([int(r['period']) for r in daily] == list(range(start, end + 1)), 'Incomplete daily horizon.')

    stock = {(int(r['period']), r['node_id'], r['product_id']): int(r['closing_units']) for r in inventory}
    inv = {(int(r['period']), r['node_id'], r['product_id']): r for r in inventory}
    caps = {(int(r['period']), r['from_node'], r['to_node']): r for r in capacity}
    audit_days, blocker_rows, signature_rows = [], [], []
    for row in daily:
        day = int(row['period'])
        waiting = [r for r in orders if int(r['due_period']) <= day and
                   (not r['completion_period'] or int(r['completion_period']) > day)]
        require(len(waiting) == int(row['backlog_end_of_day']), 'Daily backlog mismatch.')
        blockers, signatures = Counter(), Counter()
        for order in waiting:
            needed = Counter()
            seat_units = 0
            for part, quantity in bom[order['order_product_id']]:
                if groups[part] == 'seat':
                    seat_units += quantity
                    for child, units in bom[part]:
                        needed['seat-supplier_prod', child] += quantity * units
                else:
                    needed['zp7', part] += quantity
            reasons = set()
            for (node, part), quantity in needed.items():
                if stock.get((day, node, part), 0) < quantity:
                    reasons.add(f'material:{node}:{part}')
            for arc, quantity in {('zp7', 'zp8'): 1, ('seat-supplier_prod', 'seat-supplier_inv'): seat_units,
                                  ('seat-supplier_inv', 'zp7'): seat_units}.items():
                c = caps[day, *arc]
                if int(c['capacity_units']) - int(c['used_units']) < quantity:
                    reasons.add('capacity:' + '->'.join(arc))
            blockers.update(reasons)
            signatures['; '.join(sorted(reasons)) or 'individually_feasible'] += 1
        assembly = caps[day, 'zp7', 'zp8']
        audit_days.append({'period': day, 'produced': int(row['produced_today']),
                           'unused_assembly_slots': int(assembly['capacity_units']) - int(assembly['used_units']),
                           'backlog': len(waiting), 'individually_feasible_waiting': signatures['individually_feasible']})
        blocker_rows.extend({'period': day, 'blocker': reason, 'affected_orders': count}
                            for reason, count in sorted(blockers.items()))
        signature_rows.extend({'period': day, 'exact_blocker_set': reason, 'orders': count}
                              for reason, count in sorted(signatures.items()))

    # A single BEV battery per BEV order is required for the car-count bound.
    battery_units = {car: sum(q for p, q in bom[car] if p == 'BEV') for car in demand}
    require(set(battery_units.values()) <= {0, 1}, 'Expected zero or one BEV battery per car.')
    require(not any(groups[p] == 'battery' and p != 'BEV' for car in demand for p, q in bom[car]),
            'Additional battery products need a generalized audit.')
    battery_demand = sum(battery_units.values())
    opening_finished = sum(r['opening_stock_units'] for r in initial if r['product_id'] == 'BEV'
                           and r['node_id'] in {'zp7', 'battery-supplier_inv'})
    existing_finished = sum(r['flow_units'] for r in existing if r['product_id'] == 'BEV'
                            and (r['from_node'], r['to_node']) in {production, transport}
                            and r['period'] + lead[r['from_node'], r['to_node']] <= end)
    components = bom['BEV']
    require(bool(components), 'Missing BEV physical BOM.')
    usable_components = Counter({p: sum(r['opening_stock_units'] for r in initial
                                       if r['node_id'] == production[0] and r['product_id'] == p)
                                 for p, units in components})
    opening_equivalents = min(usable_components[p] // units for p, units in components)
    arrival_batches = defaultdict(Counter)
    for r in existing:
        if (r['from_node'], r['to_node']) == upstream:
            arrival_batches[r['period'], r['period'] + lead[upstream]][r['product_id']] += r['flow_units']
    shipment_rows = []
    for (departure, arrival), quantities in sorted(arrival_batches.items()):
        earliest = arrival + lead[production] + lead[transport]
        equivalents = min(quantities[p] // units for p, units in components)
        if earliest <= end:
            usable_components.update(quantities)
        shipment_rows.append({'departure_period': departure, 'component_arrival': arrival,
                              'battery_equivalents': equivalents, 'earliest_assembly_receipt': earliest,
                              'usable_within_horizon': earliest <= end})
    # Optimistic quantity bound: ignores daily capacity and other-material restrictions.
    material_bound = min(usable_components[p] // units for p, units in components)
    available_batteries_bound = opening_finished + existing_finished + material_bound
    actual_used = sum(int(r['consumed_or_dispatched_units']) for r in inventory
                      if r['node_id'] == 'zp7' and r['product_id'] == 'BEV')
    completed_bev = sum(battery_units[r['order_product_id']] for r in orders if r['status'] != 'unfulfilled')
    require(actual_used == completed_bev, 'Battery consumption/order reconciliation failed.')
    car_bound = len(orders) - battery_demand + min(battery_demand, available_batteries_bound)
    battery_rows = []
    for day in range(start, end + 1):
        assembly = inv.get((day, 'zp7', 'BEV'), {})
        prod = caps[day, *production]
        dispatch = caps[day, *transport]
        # Opening plus receipts is material available before that day's production.
        material_before = min((int(inv[day, production[0], p]['opening_units']) +
                               int(inv[day, production[0], p]['receipts_units'])) // units
                              for p, units in components)
        battery_rows.append({'period': day, 'battery_orders_due': sum(battery_units[car] for car, r in demand.items() if r['period'] == day),
                             'material_equivalents_before_production': material_before,
                             'production_capacity': int(prod['capacity_units']), 'batteries_produced': int(prod['used_units']),
                             'dispatch_capacity': int(dispatch['capacity_units']), 'batteries_dispatched': int(dispatch['used_units']),
                             'assembly_opening': int(assembly.get('opening_units', 0)),
                             'assembly_receipts': int(assembly.get('receipts_units', 0)),
                             'assembly_consumed': int(assembly.get('consumed_or_dispatched_units', 0)),
                             'assembly_closing': int(assembly.get('closing_units', 0))})
    result = {'audit_checks': 'PASS', 'report_source': 'reports/scenario_battery_expedited',
              'battery_demand': battery_demand, 'opening_finished_batteries': opening_finished,
              'existing_finished_batteries': existing_finished, 'opening_component_battery_equivalents': opening_equivalents,
              'usable_component_battery_equivalents': material_bound,
              'battery_supply_quantity_bound': available_batteries_bound, 'batteries_consumed': actual_used,
              'battery_quantity_shortfall': max(0, battery_demand - available_batteries_bound),
              'optimistic_car_quantity_bound': car_bound, 'actual_completed_cars': summary['produced_units'],
              'quantity_bound_attained': car_bound == summary['produced_units'],
              'final_unfulfilled_orders': len(unfulfilled),
              'final_unfulfilled_bev_orders': sum(battery_units[r['order_product_id']] for r in unfulfilled),
              'unused_assembly_slots_total': sum(r['unused_assembly_slots'] for r in audit_days),
              'limitations': ['Day-end blocker counts may overlap and test orders individually without reserving resources.',
                              'The quantity bound applies only to unchanged opening stock, shipments, lead times and order BOM.',
                              'Attaining this bound establishes horizon volume only; it does not prove optimal on-time completion, backlog-days or cost.',
                              'Earliest receipts after Day 74 are lead-time calculations; post-horizon capacity is not established.'],
              'input_sha256': {n: hashlib.sha256((reports / n).read_bytes()).hexdigest()
                               for n in ['summary.json', 'daily_summary.csv', 'order_results.csv', 'inventory_ledger.csv', 'capacity_ledger.csv']}}
    out = root / 'reports/diagnosis_expedited'
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in [('daily_resource_audit.csv', audit_days), ('daily_blockers.csv', blocker_rows),
                       ('daily_blocker_sets.csv', signature_rows), ('battery_timeline.csv', battery_rows),
                       ('battery_shipments.csv', shipment_rows)]:
        require(bool(rows), f'No rows for {name}.')
        write_csv(out / name, rows, list(rows[0]))
    write_csv(out / 'terminal_pipeline_copy.csv', pipeline,
              ['arrival_period', 'from_node', 'to_node', 'product_id', 'quantity', 'start_period', 'origin'])
    (out / 'diagnosis_summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    lines = ['STEP 6A - EXPEDITED BACKLOG AUDIT', 'DAY | PRODUCED | UNUSED ASSEMBLY | BACKLOG | FEASIBLE WAITING']
    lines += [f"{r['period']} | {r['produced']} | {r['unused_assembly_slots']} | {r['backlog']} | {r['individually_feasible_waiting']}" for r in audit_days]
    lines += ['', 'BATTERY QUANTITY RECONCILIATION']
    for key in ['battery_demand', 'opening_finished_batteries', 'existing_finished_batteries',
                'opening_component_battery_equivalents', 'usable_component_battery_equivalents',
                'battery_supply_quantity_bound', 'batteries_consumed', 'battery_quantity_shortfall',
                'optimistic_car_quantity_bound', 'actual_completed_cars', 'quantity_bound_attained',
                'final_unfulfilled_orders', 'final_unfulfilled_bev_orders', 'unused_assembly_slots_total', 'audit_checks']:
        lines.append(f'{key}: {result[key]}')
    lines += ['', 'BATTERY PRODUCTION AND ARRIVALS', 'DAY | MATERIAL BEFORE | PRODUCED/CAPACITY | ASSEMBLY RECEIPTS | ASSEMBLY CLOSING']
    lines += [f"{r['period']} | {r['material_equivalents_before_production']} | {r['batteries_produced']}/{r['production_capacity']} | {r['assembly_receipts']} | {r['assembly_closing']}" for r in battery_rows]
    lines += ['', 'DAY-END BLOCKERS ON UNDERUSED ASSEMBLY DAYS']
    underused = {r['period'] for r in audit_days if r['unused_assembly_slots'] > 0}
    lines += [f"Day {r['period']} | {r['exact_blocker_set']} | {r['orders']} orders" for r in signature_rows if r['period'] in underused]
    lines += ['', 'EXISTING COMPONENT SHIPMENTS (SCENARIO LEAD TIMES)']
    lines += [f"Departure {r['departure_period']} | arrival {r['component_arrival']} | equivalents {r['battery_equivalents']} | earliest assembly receipt {r['earliest_assembly_receipt']}" for r in shipment_rows]
    lines += ['', *result['limitations'], '', 'Saved: reports/diagnosis_expedited/']
    text = '\n'.join(lines) + '\n'
    (out / 'diagnosis_console.txt').write_text(text, encoding='utf-8')
    print(text)
    return result


if __name__ == '__main__':
    main()
