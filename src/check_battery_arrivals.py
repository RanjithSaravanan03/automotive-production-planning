from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "processed" / "planning.sqlite"

with sqlite3.connect(DATABASE) as connection:
    connection.row_factory = sqlite3.Row

    arrivals = connection.execute("""
        SELECT
            product_id,
            departure_period,
            lead_time_days,
            arrival_period,
            flow_units,
            horizon_status
        FROM initial_arrivals
        WHERE to_node = 'battery-supplier_prod'
        ORDER BY arrival_period, product_id
    """).fetchall()

    production_lead = connection.execute("""
        SELECT lead_time_days
        FROM arcs
        WHERE from_node = 'battery-supplier_prod'
          AND to_node = 'battery-supplier_inv'
    """).fetchone()[0]

    transfer_lead = connection.execute("""
        SELECT lead_time_days
        FROM arcs
        WHERE from_node = 'battery-supplier_inv'
          AND to_node = 'zp7'
    """).fetchone()[0]

print("EXISTING BATTERY-COMPONENT ARRIVALS")
for row in arrivals:
    print(
        f"{row['product_id']} | "
        f"Departure: {row['departure_period']} | "
        f"Arrival: {row['arrival_period']} | "
        f"Units: {row['flow_units']} | "
        f"{row['horizon_status']}"
    )

if arrivals:
    first_arrival = min(row["arrival_period"] for row in arrivals)
    earliest_assembly_receipt = (
        first_arrival + production_lead + transfer_lead
    )

    print(f"\nFirst replacement-material arrival: Day {first_arrival}")
    print(f"Battery production lead time: {production_lead} day(s)")
    print(f"Transfer to assembly: {transfer_lead} day(s)")
    print(
        "Earliest assembly receipt from these materials: "
        f"Day {earliest_assembly_receipt}"
    )
    print("Actual quantities remain subject to materials and daily capacity.")
