from pathlib import Path
import contextlib
import io
import json
import shutil
import sqlite3
import tempfile

from baseline_14day import run

ROOT = Path(__file__).resolve().parents[1]

for transit_days in (20, 16):
    print(f"\nSTARTING SENSITIVITY: transit_days={transit_days}", flush=True)
    name = f"sensitivity_no_unscheduled_transit_{transit_days}"
    output = ROOT / "reports" / name

    with tempfile.TemporaryDirectory() as directory:
        scenario_root = Path(directory)
        (scenario_root / "config").mkdir()
        (scenario_root / "data" / "processed").mkdir(parents=True)

        policy = json.loads(
            (ROOT / "config" / "baseline_policy.json").read_text(
                encoding="utf-8-sig"
            )
        )

        policy["policy_name"] = name
        policy["supplier_production"]["after_fixed_schedule"] = (
            "no_unscheduled_production"
        )

        (scenario_root / "config" / "baseline_policy.json").write_text(
            json.dumps(policy, indent=2),
            encoding="utf-8",
        )

        database = scenario_root / "data" / "processed" / "planning.sqlite"

        with contextlib.closing(
            sqlite3.connect(ROOT / "data" / "processed" / "planning.sqlite")
        ) as source:
            with contextlib.closing(sqlite3.connect(database)) as destination:
                source.backup(destination)

                cursor = destination.execute("""
                    UPDATE arcs
                    SET lead_time_days = ?
                    WHERE from_node = 'battery-supplier_trans'
                      AND to_node = 'battery-supplier_prod'
                """, (transit_days,))

                if cursor.rowcount != 1:
                    raise ValueError("Expected one battery-component route.")

                destination.commit()

        with contextlib.redirect_stdout(io.StringIO()):
            result = run(scenario_root)

        shutil.copytree(
            scenario_root / "reports" / "baseline_14day",
            output,
            dirs_exist_ok=True,
        )

    result["scenario_name"] = name
    result["limitations"] = [
        text for text in result["limitations"]
        if not text.startswith("No new 20/23-day")
    ]
    result["limitations"].append(
        f"Battery-component transit is {transit_days} days; "
        "existing departure dates and quantities are unchanged. "
        "No new upstream departures are added."
    )

    (output / "summary.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    (output / "scenario_assumptions.json").write_text(
        json.dumps({
            "battery_component_transit_days": transit_days,
            "post_day_70_policy": "no_unscheduled_production",
            "expedited_transport": (
                "Hypothetical; availability and cost not established."
                if transit_days == 16 else "Not applied."
            ),
        }, indent=2),
        encoding="utf-8",
    )

    print(f"\nSCENARIO: {name}")
    for metric in (
        "produced_units",
        "unfulfilled_units",
        "on_time_units",
        "on_time_pct",
        "backlog_unit_days",
        "feasibility_checks",
    ):
        print(f"{metric}: {result[metric]}")

    print(f"Saved: {output}")
