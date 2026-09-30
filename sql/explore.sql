-- These queries are descriptive. They do not establish plan feasibility.
-- Run with SQLite or DB Browser for SQLite against data/processed/planning.sqlite.

-- Demand by due day and whether the configuration requires a battery.
SELECT d.due_period,
       CASE WHEN EXISTS (
           SELECT 1 FROM configuration_bom b
           WHERE b.configuration_id=d.configuration_id AND b.component_product_id='BEV'
       ) THEN 'Battery required' ELSE 'No BEV component in supplied BOM' END AS demand_type,
       SUM(d.demand_units) AS demand_units
FROM demand_by_configuration d
GROUP BY d.due_period, demand_type
ORDER BY d.due_period, demand_type;

-- Assembly capacity versus due-day demand (does not account for component shortages).
SELECT c.period, c.capacity_units, SUM(d.demand_units) AS demand_units,
       c.capacity_units-SUM(d.demand_units) AS nominal_capacity_headroom
FROM capacity_at_arc c JOIN demands d ON d.period=c.period
WHERE c.from_node='zp7' AND c.to_node='zp8'
GROUP BY c.period,c.capacity_units ORDER BY c.period;

-- Previously dispatched components arriving inside the planning horizon.
SELECT to_node, product_id, arrival_period, SUM(flow_units) AS arrival_units
FROM initial_arrivals WHERE horizon_status='within_horizon'
GROUP BY to_node,product_id,arrival_period ORDER BY arrival_period,to_node,product_id;

-- Nominal gross component demand; no stock netting or lead-time offset applied.
SELECT p.product_group, SUM(g.gross_requirement_units) AS units_required
FROM direct_component_gross_demand g JOIN products p USING(product_id)
GROUP BY p.product_group;
