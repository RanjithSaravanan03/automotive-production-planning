from pathlib import Path
import sqlite3

# Locate the project database.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "data" / "processed" / "planning.sqlite"

if not DATABASE.exists():
    raise FileNotFoundError(
        "Database not found. Run src/prepare_data.py first."
    )

connection = sqlite3.connect(DATABASE)
connection.row_factory = sqlite3.Row


def display(title, rows):
    print(f"\n{title}")
    print("-" * len(title))

    if not rows:
        print("No records found.")
        return

    for row in rows:
        print(" | ".join(f"{key}: {row[key]}" for key in row.keys()))


# Select a configuration requiring a battery.
selected = connection.execute("""
    SELECT configuration_id
    FROM configuration_bom
    WHERE component_product_id = 'BEV'
    ORDER BY configuration_id
    LIMIT 1
""").fetchone()

if selected is None:
    raise ValueError("No battery-requiring configuration found.")

configuration_id = selected["configuration_id"]
print(f"Selected configuration: {configuration_id}")


# 1. How many cars of this configuration are due each day?
demand = connection.execute("""
    SELECT due_period, SUM(demand_units) AS cars_required
    FROM demand_by_configuration
    WHERE configuration_id = ?
    GROUP BY due_period
    ORDER BY due_period
""", (configuration_id,)).fetchall()

display("1. DEMAND BY DUE DAY", demand)


# 2. What components are needed to build one car?
components = connection.execute("""
    SELECT
        b.component_product_id,
        p.product_group,
        b.component_quantity AS units_per_car
    FROM configuration_bom b
    JOIN products p
        ON b.component_product_id = p.product_id
    WHERE b.configuration_id = ?
    ORDER BY p.product_group
""", (configuration_id,)).fetchall()

display("2. COMPONENTS REQUIRED PER CAR", components)


# 3. What is the opening stock at final assembly?
# LEFT JOIN keeps components that have no stock record.
opening_stock = connection.execute("""
    SELECT
        b.component_product_id,
        i.opening_stock_units,
        CASE
            WHEN i.product_id IS NULL THEN 'No source stock record'
            ELSE 'Recorded opening stock'
        END AS stock_status
    FROM configuration_bom b
    LEFT JOIN initial_inventories i
        ON b.component_product_id = i.product_id
       AND i.node_id = 'zp7'
       AND i.period = 60
    WHERE b.configuration_id = ?
    ORDER BY b.component_product_id
""", (configuration_id,)).fetchall()

display("3. OPENING STOCK AT FINAL ASSEMBLY", opening_stock)


# 4. Which previously dispatched components will arrive there?
arrivals = connection.execute("""
    SELECT
        a.product_id,
        a.arrival_period,
        SUM(a.flow_units) AS arriving_units
    FROM initial_arrivals a
    JOIN configuration_bom b
        ON a.product_id = b.component_product_id
    WHERE b.configuration_id = ?
      AND a.to_node = 'zp7'
      AND a.horizon_status = 'within_horizon'
    GROUP BY a.product_id, a.arrival_period
    ORDER BY a.arrival_period, a.product_id
""", (configuration_id,)).fetchall()

display("4. EXISTING FLOWS ARRIVING AT FINAL ASSEMBLY", arrivals)


# 5. What is the total assembly capacity available each day?
capacity = connection.execute("""
    SELECT period, capacity_units
    FROM capacity_at_arc
    WHERE from_node = 'zp7'
      AND to_node = 'zp8'
    ORDER BY period
""").fetchall()

display("5. DAILY ASSEMBLY CAPACITY — ALL CONFIGURATIONS", capacity)

# 6. Trace the seat supply route.
seat_routes = connection.execute("""
    SELECT
        a.from_node,
        a.to_node,
        a.product_group,
        a.lead_time_days,
        c.capacity_units AS day_61_capacity
    FROM arcs a
    JOIN capacity_at_arc c
        ON a.from_node = c.from_node
       AND a.to_node = c.to_node
    WHERE a.product_group IN ('seat', 'seat_component')
      AND c.period = 61
    ORDER BY a.from_node
""").fetchall()

display("6. SEAT SUPPLY ROUTES AND DAY 61 CAPACITY", seat_routes)


# 7. Find physical components needed to produce one Q4H seat.
seat_bom = connection.execute("""
    SELECT
        parent_product_id,
        component_product_id,
        component_quantity
    FROM physical_bom
    WHERE parent_product_id = 'Q4H'
""").fetchall()

display("7. COMPONENTS REQUIRED FOR ONE Q4H SEAT", seat_bom)


# 8. Find opening stock of Q4H and its components across all nodes.
seat_stock = connection.execute("""
    SELECT
        node_id,
        product_id,
        opening_stock_units
    FROM initial_inventories
    WHERE product_id = 'Q4H'
       OR product_id IN (
           SELECT component_product_id
           FROM physical_bom
           WHERE parent_product_id = 'Q4H'
       )
    ORDER BY node_id, product_id
""").fetchall()

display("8. SEAT AND SEAT-COMPONENT OPENING STOCK", seat_stock)


# 9. Check existing arrivals of the relevant seat components.
seat_arrivals = connection.execute("""
    SELECT
        to_node,
        product_id,
        arrival_period,
        flow_units,
        horizon_status
    FROM initial_arrivals
    WHERE product_id IN (
        SELECT component_product_id
        FROM physical_bom
        WHERE parent_product_id = 'Q4H'
    )
    ORDER BY arrival_period, to_node
""").fetchall()

display("9. EXISTING ARRIVALS OF Q4H COMPONENTS", seat_arrivals)

# 10. Compare Day 61 demand across all configurations
# with known component availability at final assembly.
day_61_comparison = connection.execute("""
    WITH requirements AS (
        SELECT
            product_id,
            SUM(gross_requirement_units) AS required_units
        FROM direct_component_gross_demand
        WHERE due_period = 61
        GROUP BY product_id
    ),
    opening AS (
        SELECT
            product_id,
            SUM(opening_stock_units) AS opening_units
        FROM initial_inventories
        WHERE node_id = 'zp7'
          AND period = 60
        GROUP BY product_id
    ),
    arrivals AS (
        SELECT
            product_id,
            SUM(flow_units) AS arriving_units
        FROM initial_arrivals
        WHERE to_node = 'zp7'
          AND arrival_period = 61
        GROUP BY product_id
    )
    SELECT
        r.product_id,
        p.product_group,
        r.required_units,
        o.opening_units AS recorded_opening_stock,
        COALESCE(a.arriving_units, 0) AS existing_arrivals,
        CASE
            WHEN o.opening_units IS NULL THEN NULL
            ELSE o.opening_units + COALESCE(a.arriving_units, 0)
        END AS known_available,
        CASE
            WHEN o.opening_units IS NULL THEN NULL
            ELSE o.opening_units
                 + COALESCE(a.arriving_units, 0)
                 - r.required_units
        END AS balance_before_new_flows
    FROM requirements r
    JOIN products p ON r.product_id = p.product_id
    LEFT JOIN opening o ON r.product_id = o.product_id
    LEFT JOIN arrivals a ON r.product_id = a.product_id
    ORDER BY p.product_group, r.product_id
""").fetchall()

display(
    "10. DAY 61 COMPONENT REQUIREMENTS — ALL CONFIGURATIONS",
    day_61_comparison
)


# 11. Check whether opening seat-component stock can support
# all seats required on Day 61.
seat_material_check = connection.execute("""
    WITH seat_requirements AS (
        SELECT
            g.product_id AS seat_id,
            g.gross_requirement_units AS seats_required
        FROM direct_component_gross_demand g
        JOIN products p ON g.product_id = p.product_id
        WHERE g.due_period = 61
          AND p.product_group = 'seat'
    )
    SELECT
        s.seat_id,
        s.seats_required,
        b.component_product_id,
        s.seats_required * b.component_quantity
            AS components_required,
        i.opening_stock_units AS recorded_component_stock,
        i.opening_stock_units
            - s.seats_required * b.component_quantity
            AS balance_using_opening_stock
    FROM seat_requirements s
    JOIN physical_bom b
        ON s.seat_id = b.parent_product_id
    LEFT JOIN initial_inventories i
        ON b.component_product_id = i.product_id
       AND i.node_id = 'seat-supplier_prod'
       AND i.period = 60
    ORDER BY s.seat_id
""").fetchall()

display(
    "11. DAY 61 SEAT MATERIAL CHECK — ALL CONFIGURATIONS",
    seat_material_check
)

connection.close()
