# Data dictionary

Generated from the included source CSVs. All numeric fields here are integers; identifiers remain text.
Raw column names and values remain in data/source. Clean fields are in data/processed and planning.sqlite.
Group aliases: seat_componment → seat_component; battery_componment → battery_component.
Product IDs containing componment are preserved exactly.

## products

28,049 rows; 3 columns. Key: product_id.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 28,049 distinct |
| group_g | product_group | text | Source group; two misspellings corrected in normalized labels only. | 7 distinct |
| transportation_size_s | transportation_size | integer | Explicit transport-equipment size parameter; all zero in this workbook. | 1 distinct; min 0, max 0 |

## nodes

12 rows; 1 columns. Key: node_id.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| node_n | node_id | text | Network location or stage identifier. | 12 distinct |

## nodes_inflow

44 rows; 2 columns. Key: node_id, product_id.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| node_n | node_id | text | Network location or stage identifier. | 4 distinct |
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 44 distinct |

## arcs

11 rows; 4 columns. Key: from_node, to_node.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| starting_node_i | from_node | text | Starting node of the directed connection. | 11 distinct |
| ending_node_j | to_node | text | Ending node of the directed connection. | 8 distinct |
| process_lead_time_l_ij | lead_time_days | integer | Days from departure/process start to arrival/completion. | 5 distinct; min 0, max 23 |
| group_g | product_group | text | Source group; two misspellings corrected in normalized labels only. | 7 distinct |

## capacity_at_arc

154 rows; 4 columns. Key: from_node, to_node, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| starting_node_i | from_node | text | Starting node of the directed connection. | 11 distinct |
| ending_node_j | to_node | text | Ending node of the directed connection. | 8 distinct |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 14 distinct; min 61, max 74 |
| capacity_c_ijt | capacity_units | integer | Maximum total flow units on this connection/day; units depend on the product group. | 6 distinct; min 0, max 14700 |

## max_flow_product_per_arc

365 rows; 5 columns. Key: from_node, to_node, product_id, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| starting_node_i | from_node | text | Starting node of the directed connection. | 2 distinct |
| ending_node_j | to_node | text | Ending node of the directed connection. | 2 distinct |
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 37 distinct |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 10 distinct; min 61, max 70 |
| planned_flow | planned_flow_units | integer | Supplied schedule quantity; fixed versus maximum interpretation remains open. | 180 distinct; min 1, max 709 |

## max_flow_group_per_arc

20 rows; 5 columns. Key: from_node, to_node, product_group, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| starting_node_i | from_node | text | Starting node of the directed connection. | 2 distinct |
| ending_node_j | to_node | text | Ending node of the directed connection. | 2 distinct |
| group_g | product_group | text | Source group; two misspellings corrected in normalized labels only. | 2 distinct |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 10 distinct; min 61, max 70 |
| planned_flow | planned_flow_units | integer | Supplied schedule quantity; fixed versus maximum interpretation remains open. | 1 distinct; min 2000, max 2000 |

## operations

15 rows; 7 columns. Key: node_id, input_group, output_group.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| node_n | node_id | text | Network location or stage identifier. | 12 distinct |
| input_product_group_x | input_group | text | Group consumed by the operation. | 7 distinct |
| output_product_group_y | output_group | text | Group produced or passed through by the operation. | 7 distinct |
| input_quantity_in_nxy | input_quantity | integer | General group input quantity; do not multiply by BOM quantity when beta=1. | 2 distinct; min 1, max 20 |
| output_quantity_out_nxy | output_quantity | integer | General output quantity for the operation. | 1 distinct; min 1, max 1 |
| alpha_nxy | alpha | integer | Simultaneous-output parameter; all zero in supplied data. | 1 distinct; min 0, max 0 |
| beta_nxy | beta | integer | BOM-specific quantity selector; retain as provided. | 2 distinct; min 0, max 1 |

## BOM

87,059 rows; 3 columns. Key: parent_product_id, component_product_id.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| mother | parent_product_id | text | Parent item in the source BOM, including identity records. | 28,049 distinct |
| child | component_product_id | text | Child item in the source BOM, including identity records. | 49 distinct |
| individual_input_quantity_q_mc | component_quantity | integer | Child units required per parent for the relevant operation. | 4 distinct; min 1, max 10 |

## demands

28,000 rows; 4 columns. Key: node_id, product_id, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| node_n | node_id | text | Network location or stage identifier. | 1 distinct |
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 28,000 distinct |
| demand_d_npt | demand_units | integer | Units required for a car ID on its due day. | 1 distinct; min 1, max 1 |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 14 distinct; min 61, max 74 |

## initial_inventories

82 rows; 6 columns. Key: node_id, product_id, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| node_n | node_id | text | Network location or stage identifier. | 5 distinct |
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 45 distinct |
| initial_inventory_I_np0 | opening_stock_units | integer | Provided opening stock at product/node in period 60. | 72 distinct; min 3, max 2480 |
| safety_stock | safety_stock_units | integer | Source safety stock setting; all zero. | 1 distinct; min 0, max 0 |
| max_inventory | max_inventory_units | integer | Source stock upper setting; all 99999, not evidence of physical space. | 1 distinct; min 99999, max 99999 |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 1 distinct; min 60, max 60 |

## initial_flows

117 rows; 5 columns. Key: from_node, to_node, product_id, period.

| Source column | Clean column | Type | Meaning | Observed coverage |
|---|---|---|---|---|
| starting_node_i | from_node | text | Starting node of the directed connection. | 8 distinct |
| ending_node_j | to_node | text | Ending node of the directed connection. | 6 distinct |
| product_p | product_id | text | Product identifier; text, including numeric-looking car order IDs. | 45 distinct |
| period_t | period | integer | Relative day index; not an Excel calendar date. | 5 distinct; min 39, max 60 |
| initial_flow | flow_units | integer | Quantity previously dispatched or started; arrival requires lead-time shift. | 99 distinct; min 2, max 9470 |

## Derived tables

| Table | Grain and meaning |
|---|---|
| order_configuration_map | One source demand record mapped to its direct-BOM configuration, node and due period. |
| configuration_bom | One component and quantity per configuration. Configuration IDs are stable hashes of sorted direct BOM entries. |
| demand_by_configuration | Demand units grouped by configuration, delivery node and due period. |
| physical_bom | Source BOM excluding parent=child rows, for component explosion. |
| identity_bom | Parent=child source rows preserved for pass-through semantics. |
| initial_arrivals | Each initial flow plus computed arrival day and before/within/after-horizon label. |
| direct_component_gross_demand | Direct assembly component needs by original due day, without stock netting or lead-time offsets. |
