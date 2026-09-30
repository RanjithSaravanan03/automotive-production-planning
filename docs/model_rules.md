> Historical planning document from the starter phase. Some pending stages and open decisions below have since been resolved. Read the root README and `methodology.md` for the current implementation and assumptions.

# Model rules and decisions

## Evidence hierarchy

Workbook values govern this implementation. Research documentation informs field semantics;
illustrative paper numbers must not overwrite uploaded values. New policies remain explicit
project assumptions. No optimizer is released until the open decisions below are resolved.

## Source-informed interpretation

The paper defines day-indexed flows and arrival through a lead-time shift. Its beta flag
selects product-specific BOM quantities in place of group-level input quantities. Its case
uses fixed supplier production schedules. Alpha controls simultaneous output groups; this
workbook uses zero throughout. Transportation size supports an optional explicit vehicle
dimension, which is inactive here. The paper's data-generation discussion describes a
simulation informed by industrial exports and a case study. See sources.md, sections 3,
4.4, 4.6 and 4.7. These descriptions inform rules; numerical inputs come from the workbook.

## Implemented data rules

- Periods remain integer relative days; no invented calendar dates or weekends.
- Initial-flow arrival_period = departure_period + arc lead_time_days. Keep arrivals outside
  the horizon in the output, labelled accordingly; do not turn them into opening stock.
- Preserve original IDs, including component spellings. Only normalize the two misspelled
  group labels in the analysis layer, with explicit source-to-clean mapping.
- Preserve 49 identity BOM rows separately. Exclude self-links from physical component
  explosion; retain them for interpreting pass-through node operations.
- Battery component quantities in the physical BOM are 10, 6 and 4. Do not multiply these
  by the general input quantity 20; this would count the same conversion twice.
- Group orders only when their direct component IDs and quantities match. Preserve demand
  node, due period, original order ID and units. No customer-priority attribute is available.
- Direct gross requirements are due-day component quantities. They are not stock-netted
  purchase requirements and are not a feasible supplier schedule.
- The generated database enforces source-table keys and product/node/arc references.

## Open decisions before baseline implementation

| Question | Why it matters | Required next action |
|---|---|---|
| Are workbook planned flows fixed commitments or upper bounds? | Equality and upper-bound models permit different supply choices | Reconcile max_flow sheet names with the paper's fixed-schedule rule; document chosen policy and sensitivity |
| What do absent product records during days 61–70 mean? | A missing record could imply no scheduled production rather than freedom to produce | Define a sparse-schedule convention explicitly; do not silently impute |
| What applies after day 70? | No product/group schedule entries exist for days 71–74 | Determine rescheduling flexibility; retain daily arc capacities under any choice |
| Does an absent stock row mean zero? | Initial inventory coverage is sparse | Define allowed node-product pairs, then apply and record a zero convention if adopted |
| How are boundary-period inventories labelled? | Off-by-one errors create material too early | Define day-60 opening boundary and validate day-61 balances on a hand-worked example |
| Can orders be produced before their due day? | Early production can fill otherwise idle capacity | Use one explicit allowance for both baseline and optimizer; report early units |
| How are external inflow nodes supplied? | Unlimited replenishment cannot be assumed at intermediate nodes | Apply source-node eligibility, group compatibility and capacity; document any external-source convention |

## Correctness checks required at the planning stage

Material balance at every allowed product/node/day; nonnegative stocks; arrivals after
lead time; no double counting of initial flows; shared arc capacities; product/group
commitments; integer quantities; demand not exceeded; correct earliest completion;
terminal unfinished quantities; and identical evaluation rules for every comparison.

No negative stock, fractional cars, silently dropped orders, or solver-infeasibility
relaxations may be hidden. If the model is infeasible, report the blocking constraint.
