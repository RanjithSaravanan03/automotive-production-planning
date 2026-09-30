"""Build and validate the data foundation. Python 3.10+, standard library only.

Run: python src/prepare_data.py
This prepares inputs and diagnostics, not a feasible or optimized production plan.
"""
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from decimal import Decimal
from graphlib import TopologicalSorter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUP_ALIASES = {'seat_componment': 'seat_component', 'battery_componment': 'battery_component'}
# Original column -> normalized column, type. Product/node identifiers stay text.
SCHEMA = {
 'products': [('product_p','product_id','text'),('group_g','product_group','group'),('transportation_size_s','transportation_size','int')],
 'nodes': [('node_n','node_id','text')],
 'nodes_inflow': [('node_n','node_id','text'),('product_p','product_id','text')],
 'arcs': [('starting_node_i','from_node','text'),('ending_node_j','to_node','text'),('process_lead_time_l_ij','lead_time_days','int'),('group_g','product_group','group')],
 'capacity_at_arc': [('starting_node_i','from_node','text'),('ending_node_j','to_node','text'),('period_t','period','int'),('capacity_c_ijt','capacity_units','int')],
 'max_flow_product_per_arc': [('starting_node_i','from_node','text'),('ending_node_j','to_node','text'),('product_p','product_id','text'),('period_t','period','int'),('planned_flow','planned_flow_units','int')],
 'max_flow_group_per_arc': [('starting_node_i','from_node','text'),('ending_node_j','to_node','text'),('group_g','product_group','group'),('period_t','period','int'),('planned_flow','planned_flow_units','int')],
 'operations': [('node_n','node_id','text'),('input_product_group_x','input_group','group'),('output_product_group_y','output_group','group'),('input_quantity_in_nxy','input_quantity','int'),('output_quantity_out_nxy','output_quantity','int'),('alpha_nxy','alpha','int'),('beta_nxy','beta','int')],
 'BOM': [('mother','parent_product_id','text'),('child','component_product_id','text'),('individual_input_quantity_q_mc','component_quantity','int')],
 'demands': [('node_n','node_id','text'),('product_p','product_id','text'),('demand_d_npt','demand_units','int'),('period_t','period','int')],
 'initial_inventories': [('node_n','node_id','text'),('product_p','product_id','text'),('initial_inventory_I_np0','opening_stock_units','int'),('safety_stock','safety_stock_units','int'),('max_inventory','max_inventory_units','int'),('period_t','period','int')],
 'initial_flows': [('starting_node_i','from_node','text'),('ending_node_j','to_node','text'),('product_p','product_id','text'),('period_t','period','int'),('initial_flow','flow_units','int')]
}
KEYS = {
 'products':['product_id'], 'nodes':['node_id'], 'nodes_inflow':['node_id','product_id'],
 'arcs':['from_node','to_node'], 'capacity_at_arc':['from_node','to_node','period'],
 'max_flow_product_per_arc':['from_node','to_node','product_id','period'],
 'max_flow_group_per_arc':['from_node','to_node','product_group','period'],
 'operations':['node_id','input_group','output_group'], 'BOM':['parent_product_id','component_product_id'],
 'demands':['node_id','product_id','period'], 'initial_inventories':['node_id','product_id','period'],
 'initial_flows':['from_node','to_node','product_id','period']
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_source(directory):
    tables = {}
    for name, fields in SCHEMA.items():
        with (directory / f'{name}.csv').open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if reader.fieldnames != [x[0] for x in fields]:
                raise ValueError(f'{name}: source headers differ from expected schema')
            rows=[]
            for line, row in enumerate(reader,2):
                record={}
                for old,new,kind in fields:
                    value=row.get(old)
                    if value is None or not value.strip():
                        raise ValueError(f'{name}:{line}:{old}: missing required value')
                    if kind=='int':
                        number=Decimal(value)
                        if not number.is_finite() or number != int(number):
                            raise ValueError(f'{name}:{line}:{old}: expected finite integer')
                        value=int(number)
                    elif kind=='group': value=GROUP_ALIASES.get(value,value)
                    record[new]=value
                rows.append(record)
            tables[name]=rows
    return tables

def validate(tables, rules):
    checks=[]
    def check(name, ok, detail):
        checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    products={r['product_id']:r for r in tables['products']}
    nodes={r['node_id'] for r in tables['nodes']}
    groups={r['product_group'] for r in products.values()}
    arcs={(r['from_node'],r['to_node']):r for r in tables['arcs']}
    for name,rows in tables.items():
        keys=[tuple(r[c] for c in KEYS[name]) for r in rows]
        check(name+'.unique_keys',len(keys)==len(set(keys)),f'{len(keys)} records')
        missing=0;negative=0;unknown=0
        for r in rows:
            missing+=sum(v is None or v=='' for v in r.values())
            negative+=sum(isinstance(v,int) and v<0 for v in r.values())
            for c,v in r.items():
                ref=(products if c in ('product_id','parent_product_id','component_product_id') else
                     nodes if c in ('node_id','from_node','to_node') else
                     groups if c in ('product_group','input_group','output_group') else None)
                if ref is not None and v not in ref:unknown+=1
            if 'from_node' in r and (r['from_node'],r['to_node']) not in arcs:unknown+=1
        check(name+'.complete_nonnegative',missing==0 and negative==0,f'missing={missing}, negative={negative}')
        check(name+'.references',unknown==0,f'unknown references={unknown}')
    periods=set(range(rules['start_period'],rules['end_period']+1))
    actual={(r['from_node'],r['to_node'],r['period']) for r in tables['capacity_at_arc']}
    expected={(i,j,t) for i,j in arcs for t in periods}
    check('capacity.complete_grid',actual==expected,f'{len(actual)} actual vs {len(expected)} expected')
    check('demand.within_horizon',all(r['period'] in periods for r in tables['demands']),'all demand periods in horizon')
    check('opening_inventory.period',all(r['period']==rules['opening_inventory_period'] for r in tables['initial_inventories']),'opening period 60')
    check('opening_inventory.bounds',all(r['safety_stock_units']<=r['opening_stock_units']<=r['max_inventory_units'] for r in tables['initial_inventories']),'listed stock records within bounds')
    check('initial_flow.before_horizon',all(r['period']<rules['start_period'] for r in tables['initial_flows']),'past flow starts precede planning')
    check('bom.positive_quantities',all(r['component_quantity']>0 for r in tables['BOM']),'positive component quantities')
    physical=[r for r in tables['BOM'] if r['parent_product_id']!=r['component_product_id']]
    graph=defaultdict(set)
    for r in physical:graph[r['parent_product_id']].add(r['component_product_id'])
    try:list(TopologicalSorter(graph).static_order()); acyclic=True
    except ValueError:acyclic=False
    check('bom.physical_acyclic',acyclic,'identity rows excluded only for physical explosion')
    check('demand.has_physical_bom',all(r['product_id'] in graph for r in tables['demands']),'all demanded car IDs have components')
    check('flows.group_matches_arc',all(products[r['product_id']]['product_group']==arcs[r['from_node'],r['to_node']]['product_group'] for name in ['initial_flows','max_flow_product_per_arc'] for r in tables[name]),'flow products match arc groups')
    failures=[r for r in checks if r['status']=='FAIL']
    if failures:raise ValueError(json.dumps(failures,indent=2))
    return checks

def derive(tables, rules):
    physical=[r for r in tables['BOM'] if r['parent_product_id']!=r['component_product_id']]
    identities=[r for r in tables['BOM'] if r['parent_product_id']==r['component_product_id']]
    bom=defaultdict(list)
    for r in physical:bom[r['parent_product_id']].append((r['component_product_id'],r['component_quantity']))
    def signature(product):return tuple(sorted(bom[product]))
    demanded={r['product_id'] for r in tables['demands']}
    signatures={signature(p) for p in demanded}
    configs={s:'CFG_'+hashlib.sha256(json.dumps(s,separators=(',',':')).encode()).hexdigest()[:12] for s in signatures}
    if len(set(configs.values()))!=len(configs):raise ValueError('Configuration hash collision')
    order_map=[];aggregate=Counter()
    for r in tables['demands']:
        config=configs[signature(r['product_id'])]
        order_map.append({'order_product_id':r['product_id'],'configuration_id':config,'node_id':r['node_id'],'due_period':r['period'],'demand_units':r['demand_units']})
        aggregate[config,r['node_id'],r['period']]+=r['demand_units']
    grouped=[{'configuration_id':c,'node_id':n,'due_period':t,'demand_units':q} for (c,n,t),q in sorted(aggregate.items())]
    cbom=[{'configuration_id':configs[s],'component_product_id':p,'component_quantity':q} for s in sorted(signatures) for p,q in s]
    # Direct requirements by due day: no lead-time offset, stock netting or feasibility claims.
    gross=Counter();source_gross=Counter()
    for r in tables['demands']:
        for p,q in bom[r['product_id']]:source_gross[p,r['period']]+=q*r['demand_units']
    reverse={v:k for k,v in configs.items()}
    for r in grouped:
        for p,q in reverse[r['configuration_id']]:gross[p,r['due_period']]+=q*r['demand_units']
    original_daily=Counter();grouped_daily=Counter()
    for r in tables['demands']:original_daily[r['period']]+=r['demand_units']
    for r in grouped:grouped_daily[r['due_period']]+=r['demand_units']
    if gross!=source_gross or original_daily!=grouped_daily:raise ValueError('Aggregation conservation failed')
    # Date-index shift only; do not consume opening inventory or schedule new flows.
    arcs={(r['from_node'],r['to_node']):r for r in tables['arcs']}
    arrivals=[]
    for r in tables['initial_flows']:
        lead=arcs[r['from_node'],r['to_node']]['lead_time_days']; arrival=r['period']+lead
        status='before_horizon' if arrival<rules['start_period'] else 'after_horizon' if arrival>rules['end_period'] else 'within_horizon'
        arrivals.append({'from_node':r['from_node'],'to_node':r['to_node'],'product_id':r['product_id'],'departure_period':r['period'],'lead_time_days':lead,'arrival_period':arrival,'flow_units':r['flow_units'],'horizon_status':status})
    return {'physical_bom':physical,'identity_bom':identities,'order_configuration_map':order_map,
            'configuration_bom':sorted(cbom,key=lambda r:(r['configuration_id'],r['component_product_id'])),
            'demand_by_configuration':grouped,'initial_arrivals':arrivals,
            'direct_component_gross_demand':[{'product_id':p,'due_period':t,'gross_requirement_units':q} for (p,t),q in sorted(gross.items())]},len(configs)

def write_csv(path, rows):
    if not rows:raise ValueError(f'Empty output {path.name}')
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)

def write_database(path, tables, derived):
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        for name,rows in tables.items():
            definitions=[f'"{new}" {"INTEGER" if kind=="int" else "TEXT"} NOT NULL' for _,new,kind in SCHEMA[name]]
            definitions+=['PRIMARY KEY ('+','.join('"'+c+'"' for c in KEYS[name])+')']
            for col in rows[0]:
                if col in ('product_id','parent_product_id','component_product_id') and name!='products':definitions.append(f'FOREIGN KEY ("{col}") REFERENCES products(product_id)')
                if col in ('node_id','from_node','to_node') and name!='nodes':definitions.append(f'FOREIGN KEY ("{col}") REFERENCES nodes(node_id)')
            if 'from_node' in rows[0] and name!='arcs':definitions.append('FOREIGN KEY (from_node,to_node) REFERENCES arcs(from_node,to_node)')
            db.execute(f'CREATE TABLE "{name}" ('+','.join(definitions)+')')
            placeholders=','.join('?' for _ in rows[0]);db.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})',[tuple(r.values()) for r in rows])
        for name,rows in derived.items():
            defs=','.join(f'"{c}" {"INTEGER" if isinstance(v,int) else "TEXT"} NOT NULL' for c,v in rows[0].items())
            db.execute(f'CREATE TABLE "{name}" ({defs})');marks=','.join('?' for _ in rows[0])
            db.executemany(f'INSERT INTO "{name}" VALUES ({marks})',[tuple(r.values()) for r in rows])
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite foreign-key violation')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity check failed')

def main():
    rules=json.loads((ROOT/'config/planning_rules.json').read_text())
    source=ROOT/'data/source'; processed=ROOT/'data/processed'; reports=ROOT/'reports'
    processed.mkdir(exist_ok=True);reports.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'data/source_manifest.json').read_text())
    for name,digest in manifest['source_csv_sha256'].items():
        if sha(source/name)!=digest:raise ValueError(f'Source changed: {name}. Audit before updating the manifest.')
    tables=load_source(source)
    for name,count in manifest['audited_source_row_counts'].items():
        if len(tables[name])!=count:raise ValueError(f'{name}: source row count differs from audited workbook')
    checks=validate(tables,rules);derived,nconfigs=derive(tables,rules)
    checks.append({'check':'source.rows_match_audited_workbook','status':'PASS','detail':'All 12 worksheet row counts reconciled'})
    checks.extend([{'check':'aggregation.demand_and_components_conserved','status':'PASS','detail':'Exact day-level demand and component reconciliation'}, {'check':'configuration_hashes.unique','status':'PASS','detail':str(nconfigs)}])
    for name,rows in {**tables,**derived}.items():write_csv(processed/f'{name}.csv',rows)
    write_database(processed/'planning.sqlite',tables,derived)
    checks.append({'check':'sqlite.foreign_keys_and_integrity','status':'PASS','detail':'All declared references valid; integrity_check=ok'})
    write_csv(reports/'validation_checks.csv',checks)
    summary={'stage':'data_foundation_only','solver_ready':False,'source_worksheets':len(tables),'source_rows':sum(map(len,tables.values())),
             'total_demand_units':sum(r['demand_units'] for r in tables['demands']),'configurations':nconfigs,'configuration_due_groups':len(derived['demand_by_configuration']),
             'physical_bom_rows':len(derived['physical_bom']),'identity_bom_rows':len(derived['identity_bom']),
             'initial_arrival_status_counts':dict(Counter(r['horizon_status'] for r in derived['initial_arrivals'])),
             'checks_passed':len(checks),'checks_failed':0,
             'warnings':['Supplier schedule equality vs upper-bound treatment remains unresolved.','Missing supplier schedule entries are not imputed.','Financial costs absent.','Inventory limits are uniform 99999 and safety stock is zero.','Direct component demand is not a netted or lead-time-offset supply plan.','No optimization or baseline results yet.']}
    (reports/'data_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
