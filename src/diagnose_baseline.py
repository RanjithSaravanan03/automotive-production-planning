from pathlib import Path
from collections import Counter, defaultdict
import csv
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "baseline_14day"
DATABASE = ROOT / "data" / "processed" / "planning.sqlite"


def read_csv(filename):
    with (REPORTS / filename).open(
        newline="", encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


daily = read_csv("daily_summary.csv")
orders = read_csv("order_results.csv")
inventory = read_csv("inventory_ledger.csv")
capacity = read_csv("capacity_ledger.csv")

# Find the first day when assembly capacity was not fully used.
assembly_capacity = {
    int(row["period"]): int(row["capacity_units"])
    for row in capacity
    if row["from_node"] == "zp7"
    and row["to_node"] == "zp8"
}

first_shortfall = next(
    (
        row for row in daily
        if int(row["produced_today"])
        < assembly_capacity[int(row["period"])]
    ),
    None,
)

if first_shortfall is None:
    print("Assembly capacity was fully used on every day.")
    raise SystemExit(0)

day = int(first_shortfall["period"])
produced = int(first_shortfall["produced_today"])
available_capacity = assembly_capacity[day]

print(f"FIRST UNDERUSED ASSEMBLY DAY: {day}")
print(f"Cars produced: {produced}")
print(f"Assembly capacity: {available_capacity}")
print(f"Unused assembly slots: {available_capacity - produced}")


# Identify orders due by this day but not completed by its end.
waiting = [
    row for row in orders
    if int(row["due_period"]) <= day
    and (
        not row["completion_period"]
        or int(row["completion_period"]) > day
    )
]

print(f"Orders waiting at day end: {len(waiting)}")

# Closing material stock and remaining capacity on the selected day.
stock = {
    (row["node_id"], row["product_id"]): int(row["closing_units"])
    for row in inventory
    if int(row["period"]) == day
}

remaining_capacity = {
    (row["from_node"], row["to_node"]): (
        int(row["capacity_units"]) - int(row["used_units"])
    )
    for row in capacity
    if int(row["period"]) == day
}

with sqlite3.connect(DATABASE) as db:
    db.row_factory = sqlite3.Row

    groups = {
        row["product_id"]: row["product_group"]
        for row in db.execute(
            "SELECT product_id, product_group FROM products"
        )
    }

    bom = defaultdict(list)

    for row in db.execute("SELECT * FROM physical_bom"):
        bom[row["parent_product_id"]].append(
            (
                row["component_product_id"],
                row["component_quantity"],
            )
        )

# Check whether each waiting order could be built from remaining
# resources. Evaluate orders individually, without reserving stock.
blockers = Counter()
battery_orders = 0
individually_feasible = 0

for order in waiting:
    car = order["order_product_id"]
    required_material = Counter()
    seat_units = 0

    if any(part == "BEV" for part, quantity in bom[car]):
        battery_orders += 1

    for part, quantity in bom[car]:
        if groups[part] == "seat":
            seat_units += quantity

            for seat_part, units in bom[part]:
                required_material[
                    "seat-supplier_prod", seat_part
                ] += quantity * units
        else:
            required_material["zp7", part] += quantity

    reasons = set()

    for (node, part), quantity in required_material.items():
        # Same explicit missing-stock-as-zero baseline policy.
        if stock.get((node, part), 0) < quantity:
            reasons.add(f"Material: {part} at {node}")

    required_capacity = {
        ("zp7", "zp8"): 1,
        ("seat-supplier_prod", "seat-supplier_inv"): seat_units,
        ("seat-supplier_inv", "zp7"): seat_units,
    }

    for arc, quantity in required_capacity.items():
        if remaining_capacity[arc] < quantity:
            reasons.add(f"Capacity: {arc[0]} -> {arc[1]}")

    if not reasons:
        individually_feasible += 1

    blockers.update(reasons)

print(f"Waiting orders requiring BEV batteries: {battery_orders}")
print(
    "Waiting orders individually feasible from remaining resources: "
    f"{individually_feasible}"
)

print("\nRESOURCE CHECKS FAILING FOR WAITING ORDERS")

for reason, count in blockers.most_common():
    print(f"{reason} | affected orders: {count}")

print("\nBATTERY STOCK AT FINAL ASSEMBLY")

for row in inventory:
    if (
        row["node_id"] == "zp7"
        and row["product_id"] == "BEV"
        and int(row["period"]) <= day
    ):
        print(
            f"Day {row['period']} | "
            f"Opening: {row['opening_units']} | "
            f"Receipts: {row['receipts_units']} | "
            f"Consumed: {row['consumed_or_dispatched_units']} | "
            f"Closing: {row['closing_units']}"
        )

print(
    "\nNote: blocker counts may overlap. These are day-end "
    "resource checks, not proof of the upstream root cause."
)
