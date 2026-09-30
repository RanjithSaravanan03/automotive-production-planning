from pathlib import Path
import contextlib
import io
import json
import shutil
import sqlite3
import tempfile

from baseline_14day import run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "scenario_battery_expedited"
BASELINE_FILE = ROOT / "reports" / "baseline_14day" / "summary.json"

baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

# Run against a temporary database copy.
with tempfile.TemporaryDirectory() as directory:
    scenario_root = Path(directory)
    (scenario_root / "config").mkdir()
    (scenario_root / "data" / "processed").mkdir(parents=True)

    shutil.copy2(
        ROOT / "config" / "baseline_policy.json",
        scenario_root / "config" / "baseline_policy.json",
    )

    source_database = ROOT / "data" / "processed" / "planning.sqlite"
    scenario_database = (
        scenario_root / "data" / "processed" / "planning.sqlite"
    )

    with contextlib.closing(sqlite3.connect(source_database)) as source:
        with contextlib.closing(
            sqlite3.connect(scenario_database)
        ) as destination:
            source.backup(destination)

            cursor = destination.execute("""
                UPDATE arcs
                SET lead_time_days = 16
                WHERE from_node = 'battery-supplier_trans'
                  AND to_node = 'battery-supplier_prod'
                  AND lead_time_days = 20
            """)

            if cursor.rowcount != 1:
                raise ValueError(
                    "Expected one 20-day battery-component route."
                )

            destination.commit()

    # Reuse the same planning rules and feasibility checks.
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = run(scenario_root)

    shutil.copytree(
        scenario_root / "reports" / "baseline_14day",
        OUTPUT,
        dirs_exist_ok=True,
    )

scenario["scenario_name"] = "battery_component_transit_16_days"
scenario["limitations"] = [
    text for text in scenario["limitations"]
    if not text.startswith("No new 20/23-day")
]
scenario["limitations"].extend([
    "Hypothetical expedited route: battery-component transit is 16 days.",
    "This applies to all existing shipments on that route.",
    "No new upstream departures are added.",
    "Expedited transport availability and cost are not established.",
])

(OUTPUT / "summary.json").write_text(
    json.dumps(scenario, indent=2),
    encoding="utf-8",
)

assumptions = {
    "changed_route": "battery-supplier_trans -> battery-supplier_prod",
    "baseline_transit_days": 20,
    "scenario_transit_days": 16,
    "shipment_quantities": "unchanged",
    "shipment_departure_periods": "unchanged",
    "production_and_assembly_capacities": "unchanged",
    "planning_policy": "same as baseline",
}

(OUTPUT / "scenario_assumptions.json").write_text(
    json.dumps(assumptions, indent=2),
    encoding="utf-8",
)

print("METRIC | BASELINE | EXPEDITED | CHANGE")

for key in [
    "produced_units",
    "unfulfilled_units",
    "on_time_units",
    "on_time_pct",
    "backlog_unit_days",
]:
    before = baseline[key]
    after = scenario[key]
    print(f"{key} | {before} | {after} | {after - before:+.2f}")

print(f"\nFeasibility checks: {scenario['feasibility_checks']}")
print(f"Reports saved to: {OUTPUT}")
