"""Step 7B: build an offline interactive dashboard from Step 7A CSV exports.
Save in automotive_planning/src. Python 3.10+, standard library only.
Run: python src/build_planning_dashboard.py
Open reports/dashboard/index.html in a browser; no web server is needed.
Re-run Step 7A and this script after changing simulation reports.
"""
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Automotive Production Planning</title>
<style>
:root{--bg:#f3f6fa;--panel:#fff;--ink:#142638;--muted:#52667b;--line:#dbe4ed;--blue:#1769c2;--green:#087b66;--orange:#b96400;--red:#ba3d4b;--soft:#eaf2fb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 'Segoe UI',Arial,sans-serif}main{max-width:1400px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;flex-wrap:wrap}.eyebrow{color:var(--blue);font-size:12px;font-weight:700;letter-spacing:1.6px;text-transform:uppercase}h1{margin:4px 0;font-size:30px;line-height:1.2}h2{font-size:18px;margin:0 0 8px}p{margin:6px 0}.muted{color:var(--muted)}select{padding:10px 12px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--panel);color:var(--ink);max-width:100%}label{display:block;font-size:13px;color:var(--muted);margin-bottom:4px}.note{margin:20px 0;padding:14px 18px;border-left:4px solid var(--orange);background:#fff6e8;color:#684009;border-radius:5px}.cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:18px 0}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}.card .label{font-size:13px;color:var(--muted)}.value{font-size:28px;font-weight:650;font-variant-numeric:tabular-nums}.sub{font-size:12px;color:var(--muted);margin-top:5px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.panel.full{grid-column:1/-1}.chart{min-height:260px;width:100%}.chart svg{display:block;width:100%}.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 0;font-size:12px;color:var(--muted)}.swatch{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:5px}.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}th{color:var(--muted);font-weight:600}th:first-child,td:first-child{text-align:left}tr.active{background:var(--soft)}.snapshot-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}.mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.bar{height:6px;background:var(--line);border-radius:4px;overflow:hidden}.bar span{height:100%;display:block;background:var(--blue)}.pill{display:inline-block;padding:3px 9px;background:#e5f4ee;color:#076347;border-radius:20px;font-size:12px}.footer{margin:20px 0;color:var(--muted);font-size:12px}.chart text{font:12px 'Segoe UI',Arial,sans-serif;fill:var(--muted)}button{font:inherit;padding:8px 14px;border:1px solid var(--line);background:var(--panel);border-radius:6px;color:var(--ink);cursor:pointer}button:focus-visible,select:focus-visible{outline:3px solid var(--blue);outline-offset:3px}details{margin-top:14px}summary{cursor:pointer;color:var(--blue)}
@media(max-width:1100px){.cards{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){main{padding:16px}.grid,.mini-grid{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:24px}h1{font-size:25px}.panel{padding:14px}header>div{width:100%}header select{width:100%}}@media print{body{background:white}main{max-width:none}.panel,.card{break-inside:avoid}button{display:none}}
</style></head><body><main>
<header><div><div class="eyebrow">Operations decision support · Simulation</div><h1>Production Planning &amp; Capacity Allocation</h1><p class="muted">Days 61–74 · 28,000 customer orders · Earliest-due-date feasible heuristic</p></div><div><label for="scenario">Planning scenario</label><select id="scenario"></select></div></header>
<div class="note" id="assumption" aria-live="polite"></div>
<section class="cards" id="kpis" aria-label="Selected scenario performance" aria-live="polite"></section>
<div class="grid">
<section class="panel"><h2>Daily production against demand</h2><p class="muted">Cars per day; demand and assembly capacity are both 2,000.</p><div class="legend"><span><i class="swatch" style="background:var(--blue)"></i>Selected production</span><span><i class="swatch" style="background:var(--muted)"></i>Demand / capacity</span></div><div id="production" class="chart"></div></section>
<section class="panel"><h2>Backlog across scenarios</h2><p class="muted">Unfulfilled orders at day end; selected scenario has the thicker line.</p><div class="legend" id="backlog-legend"></div><div id="backlog" class="chart"></div></section>
<section class="panel"><h2>Battery receipts and consumption</h2><p class="muted">BEV batteries at final assembly (zp7).</p><div class="legend"><span><i class="swatch" style="background:var(--blue)"></i>Receipts</span><span><i class="swatch" style="background:var(--orange)"></i>Consumed</span><span><i class="swatch" style="background:var(--green)"></i>Closing stock</span></div><div id="batteries" class="chart"></div></section>
<section class="panel"><h2>Battery production and dispatch</h2><p class="muted">Capacity is 294 batteries daily on each route.</p><div class="legend"><span><i class="swatch" style="background:var(--blue)"></i>Production</span><span><i class="swatch" style="background:var(--green)"></i>Dispatch to assembly</span><span><i class="swatch" style="background:var(--muted)"></i>Capacity</span></div><div id="battery-process" class="chart"></div></section>
<section class="panel full"><h2>Scenario comparison</h2><p class="muted">Alternative plans for the same orders. Compare rows individually.</p><div class="tablewrap"><table id="comparison"></table></div></section>
<section class="panel full"><div class="snapshot-head"><div><h2>Daily resource snapshot</h2><p class="muted">Route utilization and battery supply at the selected day.</p></div><div><label for="day">Planning day</label><select id="day"></select></div></div><div class="mini-grid"><div><h2>Capacity used</h2><div class="tablewrap"><table id="routes"></table></div></div><div><h2>Battery inventory</h2><div class="tablewrap"><table id="stock"></table></div><p class="sub">Component quantities preserve the dataset spelling “componment”. Compare stock within each product; quantities across different components are not interchangeable.</p></div></div></section>
<section class="panel full"><h2>Daily planning ledger</h2><div class="tablewrap"><table id="daily"></table></div></section>
</div><div class="footer"><span class="pill">In-horizon feasibility checks: PASS</span><p>Scenario results depend on stated assumptions. Extra opening stock and expedited service availability, pre-horizon capacity and costs are unverified. No cost-saving or economic optimality claim.</p><details><summary>Metric definitions</summary><p>On-time % = cars completed on their due day ÷ all 28,000 orders. Fulfilment % = cars completed by Day 74 ÷ all orders. Backlog unit-days = sum of daily closing backlog. Inventory is a daily snapshot. Utilization is used capacity ÷ available capacity for the individual route. Differences in on-time percentage are percentage points.</p></details></div>
</main><script id="planning-data" type="application/json">__DATA__</script><script>
'use strict';
const D=JSON.parse(document.getElementById('planning-data').textContent);
const $=id=>document.getElementById(id),fmt=n=>Number(n).toLocaleString('en-IN'),pct=n=>Number(n).toFixed(2)+'%';
const COLORS={baseline:'#1769c2',expedited:'#b96400',buffer:'#087b66'};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let selected='expedited';
D.scenarios.forEach(s=>{const o=document.createElement('option');o.value=s.scenario_id;o.textContent=s.scenario_label;$('scenario').append(o)});$('scenario').value=selected;
for(let day=61;day<=74;day++){const o=document.createElement('option');o.value=day;o.textContent='Day '+day;$('day').append(o)}$('day').value='74';
function table(id,heads,rows,active=-1){$(id).innerHTML='<thead><tr>'+heads.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map((r,i)=>'<tr'+(i===active?' class="active"':'')+'>'+r.map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</tbody>'}
function plot(id,series,label){
 const box=$(id),w=Math.max(280,box.clientWidth),h=260,m={l:58,r:18,t:14,b:48},pw=w-m.l-m.r,ph=h-m.t-m.b;
 const all=series.flatMap(s=>s.points.map(p=>p.y)),peak=Math.max(1,...all),step=peak>1000?500:peak>300?100:peak>100?50:20,top=Math.ceil(peak/step)*step;
 const x=d=>m.l+(d-61)/13*pw,y=v=>m.t+ph-v/top*ph;
 let svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+w+' '+h+'" role="img" aria-label="'+esc(label)+'"><title>'+esc(label)+'</title>';
 for(let i=0;i<=4;i++){const v=top*i/4;svg+='<line x1="'+m.l+'" x2="'+(w-m.r)+'" y1="'+y(v)+'" y2="'+y(v)+'" stroke="#e5ebf1"/><text x="'+(m.l-8)+'" y="'+(y(v)+4)+'" text-anchor="end">'+fmt(Math.round(v))+'</text>'}
 const ticks=w<400?[61,65,69,74]:[61,63,65,67,69,71,74];ticks.forEach(d=>{svg+='<text x="'+x(d)+'" y="'+(h-25)+'" text-anchor="middle">'+d+'</text>'});svg+='<text x="'+(m.l+pw/2)+'" y="'+(h-5)+'" text-anchor="middle">Planning day</text>';
 series.forEach(s=>{svg+='<path d="'+s.points.map((p,i)=>(i?'L':'M')+x(p.x)+','+y(p.y)).join(' ')+'" fill="none" stroke="'+s.color+'" stroke-width="'+(s.width||2)+'"'+(s.dash?' stroke-dasharray="5 4"':'')+'/>';s.points.forEach(p=>{svg+='<circle cx="'+x(p.x)+'" cy="'+y(p.y)+'" r="4" fill="'+s.color+'"><title>Day '+p.x+' · '+esc(s.name)+': '+fmt(p.y)+'</title></circle>'})});svg+='</svg>';box.innerHTML=svg;
}
const points=(rows,key)=>rows.map(r=>({x:+r.period,y:+r[key]}));
function snapshot(){const day=+$('day').value;
 const routes=D.capacity.filter(r=>r.scenario_id===selected&&+r.period===day&&!(r.from_node.endsWith('_trans')));
 table('routes',['Route','Used / capacity','Utilization'],routes.map(r=>[esc(r.route),fmt(r.used_units)+' / '+fmt(r.capacity_units),pct(r.utilization_pct)+'<div class="bar"><span style="width:'+Math.min(100,+r.utilization_pct)+'%"></span></div>']));
 const stock=D.inventory.filter(r=>r.scenario_id===selected&&+r.period===day&&(r.product_id==='BEV'||r.node_id==='battery-supplier_prod'));
 table('stock',['Location / product','Opening','Receipts','Used','Closing'],stock.map(r=>[esc(r.node_id)+'<br><span class="muted">'+esc(r.product_id)+'</span>',fmt(r.opening_units),fmt(r.receipts_units),fmt(r.consumed_or_dispatched_units),fmt(r.closing_units)]));
}
function render(){selected=$('scenario').value;const scenario=D.scenarios.find(s=>s.scenario_id===selected),k=D.kpis.find(r=>r.scenario_id===selected),base=D.kpis.find(r=>r.scenario_id==='baseline');
 $('assumption').textContent=scenario.assumption_note+' Supplier policy after Day 70: demand-driven within capacity. Extra opening batteries: '+fmt(scenario.extra_opening_finished_batteries)+'.';
 const cards=[['Completed cars',fmt(k.produced_units),fmt(k.additional_completed_vs_baseline)+' additional vs baseline'],['Fulfilment',pct(k.horizon_fulfilment_pct),'Demand: '+fmt(k.demand_units)+' cars'],['On-time completion',pct(k.on_time_pct),Number(k.on_time_improvement_pp_vs_baseline).toFixed(2)+' pp vs baseline'],['Unfulfilled cars',fmt(k.unfulfilled_units),'At the end of Day 74'],['Backlog unit-days',fmt(k.backlog_unit_days),fmt(k.backlog_unit_days_reduction_vs_baseline)+' fewer vs baseline'],['Assembly utilization',pct(k.assembly_utilization_pct),'Horizon capacity: '+fmt(k.assembly_capacity_units)]];
 $('kpis').innerHTML=cards.map(c=>'<div class="card"><div class="label">'+esc(c[0])+'</div><div class="value">'+esc(c[1])+'</div><div class="sub">'+esc(c[2])+'</div></div>').join('');
 const daily=D.daily.filter(r=>r.scenario_id===selected);
 plot('production',[{name:'Production',points:points(daily,'produced_today'),color:'#1769c2',width:3},{name:'Demand / capacity',points:points(daily,'due_today'),color:'#52667b',dash:true}],scenario.scenario_label+': daily production, demand and capacity in cars');
 $('backlog-legend').innerHTML=D.scenarios.map(s=>'<span><i class="swatch" style="background:'+COLORS[s.scenario_id]+'"></i>'+esc(s.scenario_label)+'</span>').join('');
 plot('backlog',D.scenarios.map(s=>({name:s.scenario_label,points:points(D.daily.filter(r=>r.scenario_id===s.scenario_id),'backlog_end_of_day'),color:COLORS[s.scenario_id],width:s.scenario_id===selected?4:2})), 'Daily closing backlog in cars across the three scenarios');
 const batt=D.inventory.filter(r=>r.scenario_id===selected&&r.node_id==='zp7'&&r.product_id==='BEV');
 plot('batteries',[{name:'Receipts',points:points(batt,'receipts_units'),color:'#1769c2'},{name:'Consumed',points:points(batt,'consumed_or_dispatched_units'),color:'#b96400'},{name:'Closing stock',points:points(batt,'closing_units'),color:'#087b66'}],scenario.scenario_label+': battery receipts, consumption and closing inventory in batteries');
 const prod=D.capacity.filter(r=>r.scenario_id===selected&&r.from_node==='battery-supplier_prod'),dispatch=D.capacity.filter(r=>r.scenario_id===selected&&r.from_node==='battery-supplier_inv');
 plot('battery-process',[{name:'Production',points:points(prod,'used_units'),color:'#1769c2'},{name:'Dispatch',points:points(dispatch,'used_units'),color:'#087b66'},{name:'Capacity',points:points(prod,'capacity_units'),color:'#52667b',dash:true}],scenario.scenario_label+': battery production, dispatch and route capacity in batteries per day');
 table('comparison',['Scenario','Completed','On time','Late completed','Unfulfilled','On-time %','Backlog unit-days'],D.scenarios.map(s=>{const r=D.kpis.find(k=>k.scenario_id===s.scenario_id);return [esc(s.scenario_label),fmt(r.produced_units),fmt(r.on_time_units),fmt(r.late_completed_units),fmt(r.unfulfilled_units),pct(r.on_time_pct),fmt(r.backlog_unit_days)]}),D.scenarios.findIndex(s=>s.scenario_id===selected));
 table('daily',['Day','Due','Produced','Unused assembly','Closing backlog','Assembly utilization'],daily.map(r=>[r.period,fmt(r.due_today),fmt(r.produced_today),fmt(r.unused_assembly_slots),fmt(r.backlog_end_of_day),pct(r.assembly_utilization_pct)]));snapshot();
}
$('scenario').addEventListener('change',render);$('day').addEventListener('change',snapshot);
let timer;new ResizeObserver(()=>{clearTimeout(timer);timer=setTimeout(render,80)}).observe($('production'));
render();
</script></body></html>'''


def main(root=ROOT):
    source = root / 'data/dashboard'
    manifest_path = source / 'export_manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError('Run src/prepare_dashboard_data.py first to create data/dashboard/.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['export_checks'] != 'PASS':
        raise ValueError('Dashboard export checks must be PASS.')
    data = {}
    numeric = {'period','start_day','end_day','component_transit_days','extra_opening_finished_batteries',
               'demand_units','produced_units','unfulfilled_units','on_time_units','late_completed_units',
               'horizon_fulfilment_pct','on_time_pct','backlog_unit_days','assembly_capacity_units',
               'assembly_utilization_pct','additional_completed_vs_baseline','additional_on_time_vs_baseline',
               'on_time_improvement_pp_vs_baseline','backlog_unit_days_reduction_vs_baseline','due_today',
               'produced_today','cumulative_produced','backlog_end_of_day','unused_assembly_slots',
               'capacity_units','used_units','unused_units','utilization_pct','opening_units','receipts_units',
               'consumed_or_dispatched_units','closing_units'}
    for key, name in [('scenarios','scenarios.csv'),('kpis','kpi_summary.csv'),('daily','daily_performance.csv'),
                      ('capacity','capacity_utilization.csv'),('inventory','inventory_positions.csv')]:
        with (source / name).open(newline='', encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != manifest['table_row_counts'][name]:
            raise ValueError(f'{name}: row count differs from export manifest. Re-run Step 7A.')
        for row in rows:
            for field in row:
                if field in numeric:
                    row[field] = float(row[field]) if row[field] else None
        data[key] = rows
    if {r['scenario_id'] for r in data['scenarios']} != {'baseline','expedited','buffer'}:
        raise ValueError('Expected the three Step 7A scenarios.')
    payload = json.dumps(data, separators=(',',':'), ensure_ascii=True).replace('<','\\u003c')
    html = TEMPLATE.replace('__DATA__', payload)
    out = root / 'reports/dashboard'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(html, encoding='utf-8')
    print('STEP 7B - INTERACTIVE PLANNING DASHBOARD')
    print('Scenarios: 3 | Daily records: 42 | Source export checks: PASS')
    print('Saved: reports/dashboard/index.html')
    print('Open this file in your browser. It works offline.')
    print('After changing source reports, re-run prepare_dashboard_data.py and then this script.')


if __name__ == '__main__':
    main()
