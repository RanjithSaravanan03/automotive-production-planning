from pathlib import Path
from collections import defaultdict
import csv
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "processed" / "planning.sqlite"
DAY = 61

if not DATABASE.exists():
    raise FileNotFoundError("Run src/prepare_data.py first.")

db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row

# This is a single-day assembly simulation.
# It does not schedule engine, gear or battery replenishment.
stock = defaultdict(int)

# 1. Load recorded opening inventory.
for row in db.execute("""
    SELECT node_id, product_id, opening_stock_units
    FROM initial_inventories
    WHERE period = 60
"""):
    stock[row["node_id"], row["product_id"]] += (
        row["opening_stock_units"]
    )

# 2. Receive previously dispatched material arriving today.
for row in db.execute("""
    SELECT to_node, product_id, flow_units
    FROM initial_arrivals
    WHERE arrival_period = ?
""", (DAY,)):
    stock[row["to_node"], row["product_id"]] += row["flow_units"]

# Preserve stock after today's existing arrivals, before consumption.
stock_before_production = stock.copy()

# 3. Load today's shared capacities.
capacity = {}

for row in db.execute("""
    SELECT from_node, to_node, capacity_units
    FROM capacity_at_arc
    WHERE period = ?
""", (DAY,)):
    capacity[row["from_node"], row["to_node"]] = (
        row["capacity_units"]
    )

assembly_arc = ("zp7", "zp8")
seat_production_arc = ("seat-supplier_prod", "seat-supplier_inv")
seat_transfer_arc = ("seat-supplier_inv", "zp7")

original_capacity = capacity.copy()

# Confirm that same-day seat production and transfer are permitted.
for arc in (seat_production_arc, seat_transfer_arc):
    lead_time = db.execute("""
        SELECT lead_time_days
        FROM arcs
        WHERE from_node = ? AND to_node = ?
    """, arc).fetchone()

    if lead_time is None or lead_time["lead_time_days"] != 0:
        raise ValueError("This simulation requires zero-day seat routes.")

# 4. Load physical bills of materials and product groups.
bom = defaultdict(list)

for row in db.execute("SELECT * FROM physical_bom"):
    bom[row["parent_product_id"]].append(
        (row["component_product_id"], row["component_quantity"])
    )

groups = {
    row["product_id"]: row["product_group"]
    for row in db.execute("SELECT product_id, product_group FROM products")
}

# All orders have the same due day, so order ID breaks priority ties.
orders = db.execute("""
    SELECT product_id, demand_units
    FROM demands
    WHERE period = ?
    ORDER BY product_id
""", (DAY,)).fetchall()

results = []

# 5. Evaluate and allocate one order at a time.
for order in orders:
    car = order["product_id"]

    if order["demand_units"] != 1:
        raise ValueError("This first version expects one car per order.")

    material_needed = defaultdict(int)
    seat_units = 0

    for component, quantity in bom[car]:
        if groups[component] == "seat":
            # Produce seats to order from components at the supplier.
            seat_units += quantity

            if not bom[component]:
                raise ValueError(f"Missing seat BOM: {component}")

            for seat_part, part_quantity in bom[component]:
                material_needed["seat-supplier_prod", seat_part] += (
                    quantity * part_quantity
                )
        else:
            material_needed["zp7", component] += quantity

    capacity_needed = {
        assembly_arc: 1,
        seat_production_arc: seat_units,
        seat_transfer_arc: seat_units,
    }

    reasons = []

    for key, quantity in material_needed.items():
        if stock[key] < quantity:
            reasons.append(f"Insufficient {key[1]} at {key[0]}")

    for arc, quantity in capacity_needed.items():
        if capacity[arc] < quantity:
            reasons.append(f"Capacity exhausted: {arc[0]} -> {arc[1]}")

    if reasons:
        status = "Not produced"
    else:
        # Deduct resources only after every requirement passes.
        for key, quantity in material_needed.items():
            stock[key] -= quantity

        for arc, quantity in capacity_needed.items():
            capacity[arc] -= quantity

        status = "Produced"

    results.append({
        "order_product_id": car,
        "due_period": DAY,
        "status": status,
        "reason": "; ".join(reasons),
    })

# 6. Validate and save the result.
assert all(quantity >= 0 for quantity in stock.values())
assert all(quantity >= 0 for quantity in capacity.values())
assert len(results) == len(orders)

produced = sum(row["status"] == "Produced" for row in results)

report = ROOT / "reports" / "day61_baseline_orders.csv"
report.parent.mkdir(exist_ok=True)

with report.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

print(f"Day: {DAY}")
print(f"Cars due: {len(orders)}")
print(f"Cars produced: {produced}")
print(f"Cars not produced: {len(orders) - produced}")

for arc in (assembly_arc, seat_production_arc, seat_transfer_arc):
    available = original_capacity[arc]
    used = available - capacity[arc]
    utilization = used / available * 100 if available else 0

    print(
        f"{arc[0]} -> {arc[1]}: "
        f"{used}/{available} units; {utilization:.2f}% utilization"
    )

print(f"Order results saved to: {report.name}")

# 7. Create the material ledger for the activities simulated.
inventory_rows = []

for node, product in sorted(stock):
    before = stock_before_production.get((node, product), 0)
    remaining = stock[node, product]
    consumed = before - remaining

    assert consumed >= 0
    assert before == consumed + remaining

    inventory_rows.append({
        "period": DAY,
        "node_id": node,
        "product_id": product,
        "available_after_existing_arrivals": before,
        "consumed_in_simulation": consumed,
        "remaining_after_simulation": remaining,
    })

inventory_file = ROOT / "reports" / "day61_inventory_ledger.csv"

with inventory_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(inventory_rows[0]),
    )
    writer.writeheader()
    writer.writerows(inventory_rows)


# 8. Create the capacity ledger for the three modelled activities.
capacity_rows = []

for arc in (assembly_arc, seat_production_arc, seat_transfer_arc):
    available = original_capacity[arc]
    remaining = capacity[arc]
    used = available - remaining

    capacity_rows.append({
        "period": DAY,
        "from_node": arc[0],
        "to_node": arc[1],
        "available_capacity": available,
        "used_capacity": used,
        "remaining_capacity": remaining,
        "utilization_pct": (
            round(used / available * 100, 2)
            if available else None
        ),
    })

capacity_file = ROOT / "reports" / "day61_capacity_ledger.csv"

with capacity_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(capacity_rows[0]),
    )
    writer.writeheader()
    writer.writerows(capacity_rows)


# 9. Display selected balances for verification.
print("\nSELECTED REMAINING MATERIAL")

for node, product in [
    ("zp7", "BEV"),
    ("zp7", "D83"),
    ("zp7", "G1Z"),
    ("seat-supplier_prod", "componment_seat2"),
]:
    print(f"{node} | {product} | remaining: {stock[node, product]}")

print(f"\nSaved: {inventory_file.name}")
print(f"Saved: {capacity_file.name}")

db.close()

