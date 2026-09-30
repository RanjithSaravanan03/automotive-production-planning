"""Deterministic 14-day baseline, Python 3.10+, no additional packages.

Run from the project folder: python src/baseline_14day.py
Reads config/baseline_policy.json and data/processed/planning.sqlite.
Writes reports/baseline_14day/. Does not modify the database.

Replenishment heuristic: cover outstanding horizon requirements in due-date order,
netting downstream stock and in-transit supply arriving within the horizon.
This is a feasible heuristic, not a cost-optimal or time-phased MRP solution.
"""
from collections import Counter, defaultdict
from pathlib import Path
from contextlib import closing
import csv
import json
import sqlite3
import hashlib

ROOT = Path(__file__).resolve().parents[1]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def run(root=ROOT):
    policy_path = root / 'config/baseline_policy.json'
    database = root / 'data/processed/planning.sqlite'
    require(policy_path.exists(), 'Create config/baseline_policy.json from the previous step.')
    require(database.exists(), 'Run src/prepare_data.py first.')
    policy = json.loads(policy_path.read_text(encoding='utf-8-sig'))
    start, end = policy['start_period'], policy['end_period']
    require((start, end, policy['opening_inventory_period']) == (61,74,60), 'This version supports the audited 61-74 horizon only.')
    sp = policy['supplier_production']
    require((sp['fixed_schedule_start'], sp['fixed_schedule_end']) == (61,70), 'Expected fixed schedule days 61-70.')
    require(sp['recorded_quantity_treatment'] == 'fixed', 'This version implements fixed recorded production.')
    require(sp['missing_product_on_fixed_day'] == 'zero_scheduled_production', 'Unsupported sparse schedule policy.')
    mode = sp['after_fixed_schedule']
    require(mode in ('demand_driven_within_capacity','no_unscheduled_production'), 'Unsupported post-day-70 policy.')
    require(policy['inventory']['missing_opening_record'] == 'assume_zero', 'Unsupported initial stock policy.')
    require(policy['inventory']['opening_balance_interpretation'] == 'state_before_day_61', 'Unsupported inventory boundary.')
    require(policy['inventory']['receive_arrivals_before_daily_allocation'] is True, 'This version uses same-day receipts.')
    require(policy['inventory']['allow_negative_stock'] is False, 'Negative stock is not allowed.')
    require(policy['orders']['allow_early_car_production'] is False, 'This baseline does not build cars early.')
    require(policy['orders']['priority'] == ['due_period','order_product_id'], 'Unsupported priority rule.')
    require(policy['orders']['carry_unfinished_orders_forward'] and policy['orders']['skip_temporarily_infeasible_orders'], 'Unsupported backlog policy.')
    require(policy['flows']['preserve_existing_flows'] and policy['flows']['allow_same_day_zero_lead_time_flow'], 'Unsupported flow policy.')
    require(policy['flows']['arrival_rule'] == 'start_period_plus_lead_time', 'Unsupported arrival rule.')
    require(policy['flows']['consume_inputs_at_process_start'], 'Inputs must be consumed at process start.')
    require(sp['require_permitted_inputs'] and sp['respect_production_and_transport_lead_times'] and sp['avoid_new_production_unusable_within_horizon'], 'Unsupported supply constraints.')
    require(set(sp['scheduled_groups']) == {'engine','gear'}, 'Expected engine and gear schedules.')

    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        def read(name): return [dict(r) for r in db.execute(f'SELECT * FROM "{name}"')]
        tables = {n:read(n) for n in ['products','arcs','capacity_at_arc','BOM','demands','initial_inventories','initial_flows','nodes_inflow','max_flow_product_per_arc','max_flow_group_per_arc']}
    products = {r['product_id']:r['product_group'] for r in tables['products']}
    lead = {(r['from_node'],r['to_node']):r['lead_time_days'] for r in tables['arcs']}
    arc_groups = {(r['from_node'],r['to_node']):r['product_group'] for r in tables['arcs']}
    cap = {(r['from_node'],r['to_node'],r['period']):r['capacity_units'] for r in tables['capacity_at_arc']}
    bom = defaultdict(list)
    for r in tables['BOM']:
        if r['parent_product_id'] != r['component_product_id']:
            bom[r['parent_product_id']].append((r['component_product_id'],r['component_quantity']))
    external = {(r['node_id'],r['product_id']) for r in tables['nodes_inflow']}
    initial = Counter({(r['node_id'],r['product_id']):r['opening_stock_units'] for r in tables['initial_inventories']})
    limits = {(r['node_id'],r['product_id']):r['max_inventory_units'] for r in tables['initial_inventories']}
    stock = initial.copy()
    orders = sorted(tables['demands'],key=lambda r:(r['period'],r['product_id']))
    require(all(r['demand_units']==1 and r['node_id']=='zp8' for r in orders), 'Expected unit car orders at zp8.')
    require(len({r['product_id'] for r in orders})==len(orders), 'Duplicate car order IDs.')
    require(all(lead[a]==0 for a in [('zp7','zp8'),('seat-supplier_prod','seat-supplier_inv'),('seat-supplier_inv','zp7')]), 'Expected zero-day assembly/seat routes.')

    schedule = defaultdict(list)
    expected_fixed = {}
    for r in tables['max_flow_product_per_arc']:
        key = (r['from_node'],r['to_node'],r['product_id'],r['period'])
        expected_fixed[key] = r['planned_flow_units']
        schedule[r['period']].append(r)
    for r in tables['max_flow_group_per_arc']:
        total = sum(x['planned_flow_units'] for x in schedule[r['period']] if x['from_node']==r['from_node'] and x['to_node']==r['to_node'])
        require(total==r['planned_flow_units'], 'Product/group schedule totals do not match.')

    queue = defaultdict(list)
    for r in tables['initial_flows']:
        arrival = r['period'] + lead[r['from_node'],r['to_node']]
        require(arrival >= start, 'Pre-horizon initial arrival needs separate opening-stock reconciliation.')
        queue[arrival].append((r['from_node'],r['to_node'],r['product_id'],r['flow_units'],r['period'],'existing'))
    events, flow_rows, inventory_rows, capacity_rows, daily_rows = [],[],[],[],[]
    usage = Counter()
    completed = {}
    last_blockers = {}

    def change(day, event, node, product, quantity):
        stock[node,product] += quantity
        require(stock[node,product]>=0, f'Negative inventory: day {day}, {node}, {product}')
        require(stock[node,product]<=limits.get((node,product),float('inf')), 'Recorded inventory limit exceeded.')
        events.append({'period':day,'event':event,'node_id':node,'product_id':product,'quantity_change':quantity})

    def inputs(arc, product):
        if arc[0]=='zp7' or arc[0] in ('battery-supplier_prod','seat-supplier_prod'):
            require(bool(bom[product]), f'Missing physical BOM: {product}')
            return bom[product]
        return [(product,1)]

    def move(day, arc, product, quantity, fixed=False):
        if not quantity: return
        require(isinstance(quantity,int) and quantity>0, 'Flow quantity must be a positive integer.')
        require(products[product]==arc_groups[arc], 'Flow product does not match arc group.')
        require(usage[arc[0],arc[1],day]+quantity<=cap[arc[0],arc[1],day], 'Arc capacity exceeded.')
        # Unlimited raw input is assumed only for listed engine/gear source pairs.
        if arc[0] in ('engine-supplier_prod','gear-supplier_prod'):
            require((arc[0],product) in external, 'Product not allowed at this external input node.')
            change(day,'external_supply',arc[0],product,quantity)
        for child,q in inputs(arc,product):
            change(day,'process_or_dispatch',arc[0],child,-quantity*q)
        usage[arc[0],arc[1],day] += quantity
        arrival = day + lead[arc]
        flow_rows.append({'start_period':day,'from_node':arc[0],'to_node':arc[1],'product_id':product,'flow_units':quantity,'arrival_period':arrival,'fixed_schedule':fixed})
        if arrival==day:
            change(day,'flow_arrival',arc[1],product,quantity)
        else:
            queue[arrival].append((*arc,product,quantity,day,'new'))

    def available_pipeline(nodes, product):
        return sum(q for t,rows in queue.items() if day<t<=end for i,j,p,q,started,origin in rows if j in nodes and p==product)

    def net_jobs(nodes, group, minimum_arrival):
        # Allocate known stock/pipeline to earliest demand before requesting more.
        coverage = {p:sum(stock[n,p] for n in nodes)+available_pipeline(nodes,p) for p,g in products.items() if g==group}
        jobs = []
        if minimum_arrival>end: return jobs
        for order in orders:
            if order['product_id'] in completed: continue
            for p,q in bom[order['product_id']]:
                if products[p]!=group: continue
                covered = min(coverage[p],q)
                coverage[p] -= covered
                if q>covered: jobs.append((order['period'],order['product_id'],p,q-covered))
        return sorted(jobs)

    for day in range(start,end+1):
        opening = stock.copy()
        event_start = len(events)
        for i,j,p,q,started,origin in queue.pop(day,[]):
            change(day,'existing_arrival' if origin=='existing' else 'flow_arrival',j,p,q)

        # Scheduled supplier production is mandatory within the fixed window.
        for r in sorted(schedule.get(day,[]),key=lambda r:(r['from_node'],r['product_id'])):
            move(day,(r['from_node'],r['to_node']),r['product_id'],r['planned_flow_units'],fixed=True)

        # Beyond the fixed window, produce only outstanding usable requirements.
        if day>sp['fixed_schedule_end'] and mode=='demand_driven_within_capacity':
            for group in ('engine','gear'):
                arc=(f'{group}-supplier_prod',f'{group}-supplier_inv')
                downstream={'zp7',arc[1]}
                assembly_arrival=day+lead[arc]+lead[arc[1],'zp7']
                for due,order_id,p,q in net_jobs(downstream,group,assembly_arrival):
                    room=cap[(*arc,day)]-usage[(*arc,day)]
                    move(day,arc,p,min(q,room))

        # Battery production consumes 10/6/4 physical cell quantities.
        arc=('battery-supplier_prod','battery-supplier_inv')
        for due,order_id,p,q in net_jobs({'zp7',arc[1]},'battery',day+lead[arc]+lead[arc[1],'zp7']):
            material=min(stock[arc[0],child]//units for child,units in bom[p])
            quantity=min(q,material,cap[(*arc,day)]-usage[(*arc,day)])
            move(day,arc,p,quantity)

        # Dispatch available components, sharing each supplier's arc capacity.
        for group in ('engine','gear','battery'):
            arc=(f'{group}-supplier_inv','zp7')
            for due,order_id,p,q in net_jobs({'zp7'},group,day+lead[arc]):
                quantity=min(q,stock[arc[0],p],cap[(*arc,day)]-usage[(*arc,day)])
                move(day,arc,p,quantity)

        # Assemble due/backlogged cars; seats are made and moved just in time.
        produced_today = 0
        for order in orders:
            car=order['product_id']
            if car in completed or order['period']>day: continue
            reasons=[]; seat_make=[]; needed=Counter(); seat_count=0
            for p,q in bom[car]:
                if products[p]=='seat':
                    seat_count+=q;seat_make.append((p,q))
                    for child,n in bom[p]:needed['seat-supplier_prod',child]+=q*n
                else:needed['zp7',p]+=q
            for key,q in needed.items():
                if stock[key]<q:reasons.append('material:'+key[0]+':'+key[1])
            required_arcs={('zp7','zp8'):1,('seat-supplier_prod','seat-supplier_inv'):seat_count,('seat-supplier_inv','zp7'):seat_count}
            for arc,q in required_arcs.items():
                if usage[(*arc,day)]+q>cap[(*arc,day)]:reasons.append('capacity:'+arc[0]+'->'+arc[1])
            if reasons:
                last_blockers[car]='; '.join(reasons);continue
            for seat,q in seat_make:
                move(day,('seat-supplier_prod','seat-supplier_inv'),seat,q)
                move(day,('seat-supplier_inv','zp7'),seat,q)
            move(day,('zp7','zp8'),car,1)
            change(day,'order_fulfilment','zp8',car,-1)
            completed[car]=day;produced_today+=1

        # Save exact stock roll-forwards, excluding per-order zero car inventory.
        incoming=Counter();outgoing=Counter()
        for event in events[event_start:]:
            key=event['node_id'],event['product_id'];delta=event['quantity_change']
            if delta>0:incoming[key]+=delta
            else:outgoing[key]-=delta
        for node,p in sorted(set(opening)|set(stock)):
            if products[p]=='car':continue
            require(opening[node,p]+incoming[node,p]-outgoing[node,p]==stock[node,p],'Daily inventory roll-forward failed.')
            inventory_rows.append({'period':day,'node_id':node,'product_id':p,'opening_units':opening[node,p],'receipts_units':incoming[node,p],'consumed_or_dispatched_units':outgoing[node,p],'closing_units':stock[node,p]})
        for arc in sorted(lead):
            total=cap[(*arc,day)];used=usage[(*arc,day)]
            capacity_rows.append({'period':day,'from_node':arc[0],'to_node':arc[1],'capacity_units':total,'used_units':used,'utilization_pct':round(used/total*100,2) if total else None})
        due_today=sum(r['period']==day for r in orders)
        backlog=sum(r['period']<=day and r['product_id'] not in completed for r in orders)
        daily_rows.append({'period':day,'due_today':due_today,'produced_today':produced_today,'cumulative_produced':len(completed),'backlog_end_of_day':backlog,'assembly_utilization_pct':round(produced_today/cap['zp7','zp8',day]*100,2)})

    # Independent event reconstruction, arc/lead-time and fixed schedule checks.
    replay=initial.copy()
    for event in events:
        key=event['node_id'],event['product_id'];replay[key]+=event['quantity_change']
        require(replay[key]>=0,'Event replay found negative stock.')
    require(replay==stock,'Event replay differs from final inventory.')
    flow_usage=Counter();actual_fixed={}
    for r in flow_rows:
        arc=r['from_node'],r['to_node'];t=r['start_period']
        require(r['arrival_period']==t+lead[arc],'Incorrect flow arrival date.')
        flow_usage[(*arc,t)]+=r['flow_units']
        if r['fixed_schedule']:actual_fixed[(*arc,r['product_id'],t)]=r['flow_units']
    require(actual_fixed==expected_fixed,'Scheduled production was not reproduced exactly.')
    require(all(q<=cap[key] for key,q in flow_usage.items()),'Flow reconstruction exceeds capacity.')
    require(sum(r['produced_today'] for r in daily_rows)==len(completed),'Daily order reconciliation failed.')
    require(all(t>=r['period'] for r in orders if (t:=completed.get(r['product_id'])) is not None),'Early production occurred.')
    require(daily_rows[0]['produced_today']==2000,'Day 61 does not reproduce the verified baseline.')

    order_rows=[]
    for r in orders:
        finished=completed.get(r['product_id'])
        order_rows.append({'order_product_id':r['product_id'],'due_period':r['period'],'completion_period':finished,'status':'unfulfilled' if finished is None else 'on_time' if finished==r['period'] else 'late','delay_days_if_completed':None if finished is None else finished-r['period'],'last_observed_blocker':last_blockers.get(r['product_id'],'') if finished is None else ''})
    ontime=sum(r['status']=='on_time' for r in order_rows)
    summary={'method':'earliest_due_date_feasible_heuristic','policy_name':policy['policy_name'],'post_day_70_policy':mode,'demand_units':len(orders),'produced_units':len(completed),'unfulfilled_units':len(orders)-len(completed),'on_time_units':ontime,'late_completed_units':len(completed)-ontime,'horizon_fulfilment_pct':round(len(completed)/len(orders)*100,2),'on_time_pct':round(ontime/len(orders)*100,2),'backlog_unit_days':sum(r['backlog_end_of_day'] for r in daily_rows),'feasibility_checks':'PASS','policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),'limitations':['Greedy horizon-net replenishment may hold inventory early or postpone useful replenishment when later pipeline exists.','External input is available on demand only at listed engine/gear source pairs; processing capacity remains binding.','No new 20/23-day upstream departure can support this horizon; existing in-transit shipments retained.','Seats are produced just in time. Missing stock defaults to zero.','These are simulated operational results; no cost savings, actual delivery or optimality claim.']}
    out=root/'reports/baseline_14day';out.mkdir(parents=True,exist_ok=True)
    outputs={'daily_summary.csv':daily_rows,'order_results.csv':order_rows,'inventory_ledger.csv':inventory_rows,'capacity_ledger.csv':capacity_rows,'new_flows.csv':flow_rows,'inventory_events.csv':events}
    for name,rows in outputs.items():write_csv(out/name,rows,list(rows[0]))
    terminal=[{'arrival_period':t,'from_node':i,'to_node':j,'product_id':p,'quantity':q,'start_period':s,'origin':origin} for t,rows in sorted(queue.items()) for i,j,p,q,s,origin in rows]
    write_csv(out/'terminal_pipeline.csv',terminal,['arrival_period','from_node','to_node','product_id','quantity','start_period','origin'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (out/'policy_used.json').write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
    print('DAY | DUE | PRODUCED | BACKLOG')
    for r in daily_rows:print(f"{r['period']:3} | {r['due_today']:4} | {r['produced_today']:8} | {r['backlog_end_of_day']:7}")
    print('\n'+json.dumps(summary,indent=2))
    print('\nSaved reports to reports/baseline_14day/')
    return summary

if __name__=='__main__':run()
