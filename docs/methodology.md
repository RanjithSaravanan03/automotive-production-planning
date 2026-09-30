# Methodology and evidence

## Scope

Deterministic simulation of Days 61–74, using 28,000 unit car orders due at zp8. Daily demand and assembly capacity are 2,000. The assembly arc zp7 -> zp8 has zero lead time. Order priority is (due period, product ID); early car production is prohibited.

Physical BOM explosion excludes identity rows. Preparation retains original identifiers, validates data and creates a SQLite database. The planning engine reads its own BOM inputs rather than relying on a different representation.

## Supply and timing

Opening inventory is the state before Day 61, from the period-60 records. Missing stock defaults to zero. The engine receives arrivals first, applies fixed engine/gear production, handles usable replenishment and dispatch, then assembles due/backlogged feasible cars. Materials are consumed when a process starts. External inputs are available only at listed engine/gear source pairs; processing capacity remains binding. Seats use physical inputs and are produced just in time.

Existing flows are queued using departure + current arc lead time. Scenario scripts alter the relevant arc in a temporary database, so existing arrivals are recalculated. The derived `initial_arrivals` table in the source database is not the scenario timing authority.

BEV battery inputs: 10 `componment_battery1`, 6 `componment_battery2`, 4 `componment_battery3`. Battery production and dispatch routes each allow 294 batteries daily. Each adds one day of lead time.

## Baseline diagnosis

The first unused assembly capacity is Day 64: 1,291 cars produced and 709 waiting. Individually, every waiting order fails only BEV stock at zp7. Opening components support 93 batteries and are exhausted on Day 61. The first replacement component shipment arrives on Day 66 under 20-day transit and can begin supplying assembly on Day 68.

Day-end blocker counts can overlap, and do not alone prove upstream causality. This diagnosis uses inventory roll-forwards, capacities, BOM quantities and shipment timing together.

## Expedited quantity bound

The 16-day scenario moves component arrivals to Days 62, 69 and 76, without changing quantities or departures. Their batch battery equivalents are 947, 422 and 424. Finished-battery assembly receipts can start on Days 64, 71 and 78, subject to process capacity.

Within Days 61–74:

- Opening finished batteries at assembly: 52.
- Existing finished batteries in transit: 200 + 159 = 359.
- Opening physical components: 93 battery equivalents.
- Usable component shipments: 947 + 422 = 1,369 equivalents.
- Total usable finished-battery quantity bound: 52 + 359 + 93 + 1,369 = 1,873.

Demand requires 3,003 BEV batteries, exactly one for each BEV car. Therefore at least 1,130 BEV cars remain unfulfilled under unchanged supply. Even assuming all other cars are feasible, total completions cannot exceed (28,000 - 3,003) + 1,873 = 26,870. The simulation completes this many and consumes all 1,873 batteries. It attains this horizon-volume bound. Optimality for service timing, backlog-days or cost does not follow.

On Days 64, 69, 70, 73 and 74, assembly loses respectively 415, 205, 182, 277 and 51 slots. On these days every waiting order fails only the BEV stock check. Production reaches 294 batteries daily on Days 62–64 and 69; material exhaustion causes zero production on Days 66–68 and 71–74.

## Extra-opening-stock experiment

The buffer experiment keeps 16-day transit and capacities unchanged, and adds finished BEV batteries at zp7 before Day 61. Tested extra quantities are 0, 424 and 1,130. The 424-buffer experiment is additional opening finished stock; it is not a simulation of expediting the 424-equivalent raw-component shipment.

The 1,130-buffer case raises opening BEV stock from 52 to 1,182, yielding 28,000 on-time completions and zero backlog. Since the quantity lower bound requires at least 1,130 additional usable batteries and this opening buffer achieves full fulfilment, 1,130 is sufficient and necessary within this specific additional-opening-stock experiment. It is not a general safety-stock prescription or evidence of pre-horizon manufacturability.

The full-fulfilment result holds under both tested post-Day-70 supplier policies. The original zero-buffer transit comparison likewise holds under both policies.

## Checks and evidence

The engine embeds stock nonnegativity, event replay, inventory balance, inventory limit, capacity, lead-time, fixed-schedule and order-reconciliation checks. Diagnosis/export scripts reconcile saved outputs. Data-foundation unit tests are separate from these embedded checks. The dashboard's generation and selector logic were checked programmatically, and its displayed desktop scenarios and Day-64 snapshot were reviewed using Windows screenshots. These checks do not cover every browser, viewport or exceptional input.

Reports preserve scenario assumptions, policy snapshots and detailed ledgers. The dashboard uses three alternative scenario snapshots and does not sum demand across them. It is a viewer, not a live planning solver.
