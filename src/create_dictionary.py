"""Generate source/clean field mappings and observed coverage."""
from prepare_data import ROOT,SCHEMA,KEYS,load_source

MEANINGS={
 'product_id':'Product identifier; text, including numeric-looking car order IDs.',
 'product_group':'Source group; two misspellings corrected in normalized labels only.',
 'transportation_size':'Explicit transport-equipment size parameter; all zero in this workbook.',
 'node_id':'Network location or stage identifier.',
 'from_node':'Starting node of the directed connection.',
 'to_node':'Ending node of the directed connection.',
 'lead_time_days':'Days from departure/process start to arrival/completion.',
 'period':'Relative day index; not an Excel calendar date.',
 'capacity_units':'Maximum total flow units on this connection/day; units depend on the product group.',
 'planned_flow_units':'Supplied schedule quantity; fixed versus maximum interpretation remains open.',
 'input_group':'Group consumed by the operation.',
 'output_group':'Group produced or passed through by the operation.',
 'input_quantity':'General group input quantity; do not multiply by BOM quantity when beta=1.',
 'output_quantity':'General output quantity for the operation.',
 'alpha':'Simultaneous-output parameter; all zero in supplied data.',
 'beta':'BOM-specific quantity selector; retain as provided.',
 'parent_product_id':'Parent item in the source BOM, including identity records.',
 'component_product_id':'Child item in the source BOM, including identity records.',
 'component_quantity':'Child units required per parent for the relevant operation.',
 'demand_units':'Units required for a car ID on its due day.',
 'opening_stock_units':'Provided opening stock at product/node in period 60.',
 'safety_stock_units':'Source safety stock setting; all zero.',
 'max_inventory_units':'Source stock upper setting; all 99999, not evidence of physical space.',
 'flow_units':'Quantity previously dispatched or started; arrival requires lead-time shift.'
}

def main():
    tables=load_source(ROOT/'data/source')
    lines=['# Data dictionary','',
           'Generated from the included source CSVs. All numeric fields here are integers; identifiers remain text.',
           'Raw column names and values remain in data/source. Clean fields are in data/processed and planning.sqlite.',
           'Group aliases: seat_componment → seat_component; battery_componment → battery_component.',
           'Product IDs containing componment are preserved exactly.','']
    for name,fields in SCHEMA.items():
        rows=tables[name]
        lines += [f'## {name}', '',f'{len(rows):,} rows; {len(fields)} columns. Key: '+', '.join(KEYS[name])+'.','',
                  '| Source column | Clean column | Type | Meaning | Observed coverage |','|---|---|---|---|---|']
        for old,new,kind in fields:
            values=[r[new] for r in rows];distinct=set(values)
            coverage=f'{len(distinct):,} distinct'
            if kind=='int':coverage+=f'; min {min(values)}, max {max(values)}'
            lines.append(f'| {old} | {new} | {"integer" if kind=="int" else "text"} | {MEANINGS[new]} | {coverage} |')
        lines.append('')
    lines += ['## Derived tables','',
              '| Table | Grain and meaning |','|---|---|',
              '| order_configuration_map | One source demand record mapped to its direct-BOM configuration, node and due period. |',
              '| configuration_bom | One component and quantity per configuration. Configuration IDs are stable hashes of sorted direct BOM entries. |',
              '| demand_by_configuration | Demand units grouped by configuration, delivery node and due period. |',
              '| physical_bom | Source BOM excluding parent=child rows, for component explosion. |',
              '| identity_bom | Parent=child source rows preserved for pass-through semantics. |',
              '| initial_arrivals | Each initial flow plus computed arrival day and before/within/after-horizon label. |',
              '| direct_component_gross_demand | Direct assembly component needs by original due day, without stock netting or lead-time offsets. |','']
    (ROOT/'docs/data_dictionary.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':main()
