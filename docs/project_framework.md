> Historical planning document from the starter phase. Some pending stages and open decisions below have since been resolved. Read the root README and `methodology.md` for the current implementation and assumptions.

# Project framework

## Scope

Decision owner: a production and supply planning manager at an automotive OEM.
Decision window: days 61–74, with opening state at day 60.
Demand: 28,000 individual car IDs, grouped into 104 identical direct-BOM configurations.
Keep configuration, delivery node and due day together; retain order IDs for disaggregation.
The target is a transparent planning tool with reproducible recommendations and explicit assumptions.

## Build stages and completion gates

| Stage | Work | Deliverable | Completion gate |
|---|---|---|---|
| 1. Define | Business question, objective hierarchy, constraints, KPI definitions | Scope and model rules | Distinguish source facts, assumptions and unresolved semantics |
| 2. Prepare | Preserve raw data, normalize identifiers, validate links, aggregate equivalent demand | CSVs, SQLite, dictionary, audit | Keys/references pass; exact demand and BOM conservation |
| 3. Baseline | Close supplier-policy decisions, simulate due-date-first scheduling using shared feasibility rules | Daily production, flows, stock, unmet demand | No stock/capacity/timing violation; reproducible tie-breaks |
| 4. Optimize | Integer quantities, daily material balances, capacity and supplier constraints | Optimized plan and baseline comparison | Independent feasibility audit; objective status and solver gap reported |
| 5. Scenarios | Explicit changes to capacity, availability or lead times | Before/after KPI comparison and intervention ranking | Same policy and objective unless policy change is the scenario |
| 6. Dashboard | Streamlit inputs, plans, alerts, scenario selection, CSV downloads | Working demo | UI figures reconcile to saved plan outputs |
| 7. Report | Management recommendation, limitations, code documentation, interview narrative | GitHub-ready repository and case report | Every claimed improvement linked to a validated result |

## Proposed planning logic

1. Load initial stock and schedule the arrivals of existing flows.
2. Apply supplier commitments and daily network capacities.
3. Translate car production quantities into component consumption using the BOM.
4. Track stock at each node: prior stock + arrivals - material consumed/dispatched.
5. Assign completion periods to orders; track early, on-time, late and unfulfilled units separately.
6. Compare feasible alternatives and explain the limiting resources.

Proposed objective hierarchy: first minimize unfulfilled units by day 74; then minimize late
unit-days; then minimize early unit-days. Solve these priorities sequentially so arbitrary
penalty weights do not hide trade-offs. This is a proposed project objective, not a claim
to reproduce the paper's objective. Show on-time performance even if a solution produces
more total cars by moving some orders away from their due date.

## Baseline specification to implement next

Use earliest due day, then source order ID, as deterministic priority. Process feasible
orders while skipping orders whose material is unavailable. Maintain the same permitted
early-production window and supplier policy as the optimized case. A physically infeasible
original due-day list is a demand reference, not a valid baseline. Apply a shared plan
validator to both methods, independent of the optimization model's constraint code.
Implement zero-lead-time flows in network order to avoid creating or consuming stock twice.

## KPIs and denominators

| KPI | Definition |
|---|---|
| Horizon fulfilment | Units completed by day 74 / 28,000 demand units |
| Ready by due day | Units completed on or before own due day / 28,000 |
| Exact-day adherence | Units completed on own due day / 28,000 |
| Late completed units | Completed units whose completion day exceeds own due day |
| Terminal unfulfilled units | 28,000 minus all completed units |
| Backlog unit-days | Sum of overdue outstanding units at each day end, including unresolved orders |
| Assembly utilization | Car completions / assembly capacity, at matching period or horizon |
| Arc utilization | Dispatched/processed units divided by capacity on the same arc/day; zero-capacity days are N/A |
| Schedule changes | Units completed on a different day from their due day; report early and late separately |
| Inventory | Stock by product and node; no aggregation into rupee value without item costs |

Ready-by-due-day is a completion proxy. It must not be labelled actual customer delivery
performance because customer transport and receipt records are not supplied.

## Scenario design

Start with the unmodified supplied case. Proposed overlays:
- Reduce a specified supplier's usable receipts for specified products and days.
- Delay a selected already-dispatched receipt by two days.
- Reduce a specified arc's capacity by 25% for a stated window.
- Add 10% assembly capacity; compare against adding capacity at the actual upstream bottleneck.
- Change the early-production allowance, keeping material constraints fixed.

All figures above are designed experiments, not observed events. A lead-time change to
new departures on a 20-day route may have no effect in a 14-day horizon; specify whether
an intervention changes shipments already in transit. Do not remove the same supply twice.
Report operational benefit first; ROI needs separately justified intervention costs.

## Tools and implementation order

Completed: Python standard library, CSV and SQLite.
Planned: pandas for plan analysis, PuLP with an available integer solver, Plotly and Streamlit.
Choose and record solver availability before the optimization stage. No machine learning is required.
Keep the source network in the eventual full model; use a small connected fixture for debugging only.

## What makes this an MBA project

Each scenario concludes with a concrete recommendation: which action helps, how many orders
it protects, what operational trade-off it creates and what extra evidence a manager needs
before implementing it. Maintain a transparent baseline, support conclusions with feasible
plans, and report limitations. Do not invent financial savings to strengthen the resume.
