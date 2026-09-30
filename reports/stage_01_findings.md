# Data foundation findings

## Completed

- Defined project scope, proposed objective hierarchy, KPIs and seven build stages.
- Preserved the original workbook and exported all twelve sheets as source CSVs.
- Reconciled every exported data value and row to the previously audited workbook extraction.
- Normalized column names and two product-group spellings, retaining original product IDs.
- Created nineteen SQLite tables: twelve normalized source tables and seven derived tables.
- Recorded unresolved modelling decisions explicitly instead of imputing missing schedules.

## Verified controls

| Control | Result |
|---|---:|
| Source rows across twelve sheets | 143,928 |
| Car order IDs | 28,000 |
| Total demanded car units | 28,000 |
| Direct-BOM configurations | 104 |
| Configuration, node and due-day groups | 1,286 |
| Source BOM records | 87,059 |
| Physical BOM records | 87,010 |
| Identity/pass-through BOM records | 49 |
| Prior flow records arriving during days 61–74 | 106 |
| Prior flow records arriving after day 74 | 11 |
| Automated data checks passed | 49 |
| Behavioural/conservation tests passed | 7 |

Arrival figures count records, not distinct shipments or material units. All 117 source
flow records are retained. The pipeline validates total demand and each direct component's
day-specific requirements before and after aggregation.

## Gross requirements at final assembly

| Supplied component group | Required units across original due days |
|---|---:|
| Engine | 28,000 |
| Gear | 28,000 |
| Seat | 28,000 |
| Battery | 3,003 |

These are direct gross requirements implied by the uploaded BOM. They are not purchase
orders or shortage quantities. They do not subtract stock, add process losses or offset
requirements for production/transport lead times. Do not extrapolate this simplified BOM
to a complete commercial vehicle bill of materials.

## Next implementation gate

Specify supplier fixed/maximum flow treatment and missing schedule/stock conventions.
Verify a day-60/day-61 material-balance example. Then implement the feasible baseline,
with matching policies for the later optimizer. Existing source capacity alone does not
establish that every demanded car can be built.

No baseline simulation, optimization, benefit percentage, financial saving or dashboard
has been produced in version 0.1.
