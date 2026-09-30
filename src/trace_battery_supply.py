from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "baseline_14day"


def read_csv(filename):
    with (REPORTS / filename).open(
        newline="", encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


inventory = read_csv("inventory_ledger.csv")
capacity = read_csv("capacity_ledger.csv")
flows = read_csv("new_flows.csv")

# Inspect the days leading up to the first assembly shortfall.
START_DAY = 61
END_DAY = 64

print("1. BATTERY-CELL STOCK AT THE PRODUCTION NODE")

for row in inventory:
    if (
        row["node_id"] == "battery-supplier_prod"
        and row["product_id"].startswith("componment_battery")
        and START_DAY <= int(row["period"]) <= END_DAY
    ):
        print(
            f"Day {row['period']} | {row['product_id']} | "
            f"Opening: {row['opening_units']} | "
            f"Receipts: {row['receipts_units']} | "
            f"Consumed: {row['consumed_or_dispatched_units']} | "
            f"Closing: {row['closing_units']}"
        )


print("\n2. FINISHED BATTERY STOCK AT THE SUPPLIER")

for row in inventory:
    if (
        row["node_id"] == "battery-supplier_inv"
        and row["product_id"] == "BEV"
        and START_DAY <= int(row["period"]) <= END_DAY
    ):
        print(
            f"Day {row['period']} | "
            f"Opening: {row['opening_units']} | "
            f"Receipts: {row['receipts_units']} | "
            f"Dispatched: {row['consumed_or_dispatched_units']} | "
            f"Closing: {row['closing_units']}"
        )


print("\n3. BATTERY PRODUCTION AND TRANSFER CAPACITY")

battery_arcs = {
    ("battery-supplier_prod", "battery-supplier_inv"),
    ("battery-supplier_inv", "zp7"),
}

for row in capacity:
    arc = (row["from_node"], row["to_node"])

    if (
        arc in battery_arcs
        and START_DAY <= int(row["period"]) <= END_DAY
    ):
        print(
            f"Day {row['period']} | "
            f"{arc[0]} -> {arc[1]} | "
            f"Used: {row['used_units']} / {row['capacity_units']} | "
            f"Utilization: {row['utilization_pct']}%"
        )


print("\n4. NEW BATTERY PRODUCTION AND DISPATCHES")

found = False

for row in flows:
    if (
        row["product_id"] == "BEV"
        and START_DAY <= int(row["start_period"]) <= END_DAY
    ):
        found = True
        print(
            f"Start: {row['start_period']} | "
            f"{row['from_node']} -> {row['to_node']} | "
            f"Quantity: {row['flow_units']} | "
            f"Arrival: {row['arrival_period']}"
        )

if not found:
    print("No new battery flows started during these days.")

