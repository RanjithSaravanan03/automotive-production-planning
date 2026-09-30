from pathlib import Path
import csv
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "processed" / "planning.sqlite"
REPORTS = ROOT / "reports"

START_DAY = 61
END_DAY = 74

if not DATABASE.exists():
    raise FileNotFoundError("Run src/prepare_data.py first.")

REPORTS.mkdir(exist_ok=True)

db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row


def save_csv(filename, rows):
    if not rows:
        raise ValueError(f"No records to save: {filename}")

    with (REPORTS / filename).open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def horizon_label(day):
    if day < START_DAY:
        return "Before horizon"
    if day > END_DAY:
        return "After horizon"
    return "Within horizon"


events = []

# 1. Existing flows: these were started before our planning window.
existing_flows = db.execute("""
    SELECT
        from_node,
        to_node,
        product_id,
        departure_period,
        arrival_period,
        flow_units
    FROM initial_arrivals
    ORDER BY arrival_period, to_node, product_id
""").fetchall()

for row in existing_flows:
    events.append({
        "event_type": "Existing flow",
        "from_node": row["from_node"],
        "to_node": row["to_node"],
        "product_id": row["product_id"],
        "start_period": row["departure_period"],
        "arrival_period": row["arrival_period"],
        "quantity": row["flow_units"],
        "horizon_status": horizon_label(row["arrival_period"]),
    })


# 2. Planned production: convert start days into completion days.
planned_production = db.execute("""
    SELECT
        f.from_node,
        f.to_node,
        f.product_id,
        f.period AS start_period,
        f.planned_flow_units,
        a.lead_time_days
    FROM max_flow_product_per_arc f
    JOIN arcs a
        ON f.from_node = a.from_node
       AND f.to_node = a.to_node
    ORDER BY f.period, f.from_node, f.product_id
""").fetchall()

for row in planned_production:
    completion_day = row["start_period"] + row["lead_time_days"]

    events.append({
        "event_type": "Planned production - conditional",
        "from_node": row["from_node"],
        "to_node": row["to_node"],
        "product_id": row["product_id"],
        "start_period": row["start_period"],
        "arrival_period": completion_day,
        "quantity": row["planned_flow_units"],
        "horizon_status": horizon_label(completion_day),
    })

events.sort(
    key=lambda row: (
        row["arrival_period"],
        row["to_node"],
        row["product_id"],
        row["event_type"],
    )
)

save_csv("supply_calendar.csv", events)


# 3. Check schedule coverage and compare product/group quantities.
supplier_arcs = db.execute("""
    SELECT DISTINCT from_node, to_node
    FROM max_flow_product_per_arc
    ORDER BY from_node
""").fetchall()

coverage = []

for arc in supplier_arcs:
    for day in range(START_DAY, END_DAY + 1):
        product_schedule = db.execute("""
            SELECT
                COUNT(*) AS records,
                SUM(planned_flow_units) AS total_units
            FROM max_flow_product_per_arc
            WHERE from_node = ?
              AND to_node = ?
              AND period = ?
        """, (arc["from_node"], arc["to_node"], day)).fetchone()

        group_schedule = db.execute("""
            SELECT SUM(planned_flow_units) AS total_units
            FROM max_flow_group_per_arc
            WHERE from_node = ?
              AND to_node = ?
              AND period = ?
        """, (arc["from_node"], arc["to_node"], day)).fetchone()

        daily_capacity = db.execute("""
            SELECT capacity_units
            FROM capacity_at_arc
            WHERE from_node = ?
              AND to_node = ?
              AND period = ?
        """, (arc["from_node"], arc["to_node"], day)).fetchone()

        product_total = product_schedule["total_units"]
        group_total = group_schedule["total_units"]
        capacity_units = daily_capacity["capacity_units"]

        if product_total is None or group_total is None:
            status = "Schedule missing - policy needed"
        elif product_total != group_total:
            status = "Product/group totals differ"
        elif product_total > capacity_units:
            status = "Scheduled quantity exceeds capacity"
        else:
            status = "Totals match and fit capacity"

        coverage.append({
            "from_node": arc["from_node"],
            "to_node": arc["to_node"],
            "start_period": day,
            "product_records": product_schedule["records"],
            "product_schedule_units": product_total,
            "group_schedule_units": group_total,
            "capacity_units": capacity_units,
            "status": status,
        })

save_csv("supplier_schedule_coverage.csv", coverage)


# 4. Print a concise summary.
print(f"Existing flow records: {len(existing_flows)}")
print(f"Planned production records: {len(planned_production)}")

matching = sum(
    row["status"] == "Totals match and fit capacity"
    for row in coverage
)

missing = sum(
    row["status"] == "Schedule missing - policy needed"
    for row in coverage
)

other_issues = len(coverage) - matching - missing

print(f"Supplier-days with matching schedules: {matching}")
print(f"Supplier-days requiring a schedule policy: {missing}")
print(f"Other schedule issues: {other_issues}")

print("\nSUPPLIER-DAYS REQUIRING ATTENTION")

for row in coverage:
    if row["status"] != "Totals match and fit capacity":
        print(
            f"{row['from_node']} | "
            f"Day {row['start_period']} | "
            f"{row['status']}"
        )

print("\nSaved: supply_calendar.csv")
print("Saved: supplier_schedule_coverage.csv")

db.close()
