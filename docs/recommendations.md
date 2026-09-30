# Planning findings and recommendations

## Findings supported by the simulation

1. **Material availability precedes assembly expansion.** The expedited plan leaves 1,130 BEV orders unfulfilled because usable battery supply is 1,130 units below demand. Assembly overtime alone cannot repair that quantity gap.
2. **Transit reduction improves service but does not close the gap.** The 16-day case completes 422 more cars, adds 625 on-time completions and reduces backlog unit-days by 5,484 relative to baseline. Costs and service availability are not established.
3. **A pre-horizon supply buffer can meet this deterministic demand.** An additional 1,130 finished batteries at assembly before Day 61 yields full on-time fulfilment with current in-horizon capacities. Both tested supplier policies give the same result. Its acquisition and pre-horizon capacity are hypothetical.
4. **Due dates must drive material planning.** The component arrival date alone is insufficient; add production and transfer lead times to identify when usable batteries reach assembly. The Day-76 component arrival is outside the horizon.
5. **Returning to full assembly output cannot clear backlog here.** Daily demand equals daily assembly capacity. Full output prevents further backlog growth; catching up requires earlier material availability, a demand shift, or extra usable production capacity and sufficient components.

## Recommended decision process

Maintain visibility of the time-phased battery requirements, stock and scheduled arrivals. Identify projected stockouts before releasing customer delivery promises. Evaluate confirmed material availability alongside assembly, battery production and dispatch capacities.

Before selecting an intervention, obtain actual lead-time options, transport capacity and quotes; battery procurement or pre-horizon manufacturing capacity; receiving/warehouse constraints; carrying costs; and delivery-delay penalties or contribution margins. Compare the total intervention cost against the service benefit. The current dataset does not establish an economic ranking.

Do not adopt the tested buffer as permanent safety stock without demand/lead-time uncertainty, service targets and an inventory cost model. A future time-phased MRP or optimization formulation should enforce material timing and compare policies under equal constraints.

## Scope of the current recommendation

Use the tool to expose constraints and compare documented scenarios. Treat the expedited and extra-stock cases as feasibility sensitivities requiring commercial validation. Report gains as simulated outcomes, with no realized cost-saving or factory-deployment claim.
