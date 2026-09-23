# Data dictionary and measure contract

Reporting window: **2025-01-01 through 2025-12-31**, inclusive. All costs are fictional nominal EUR with two decimal places. No currency conversion, VAT, inflation or discounting is modeled.

## Asset master

Grain in `data/raw/assets.csv`: one source row, identified by `source_row`. Raw keys may be missing or duplicated. Grain in `assets_clean.csv`: one accepted `equipment_id`.

| Field | Definition and control |
|---|---|
| `source_row` | Synthetic ingestion row identifier; preserved in quarantine and issue outputs |
| `equipment_id` | Stable `EQ-0000` key; canonicalized to uppercase, uniqueness required |
| `functional_location` | Fictional plant/unit identifier; descriptive, not an equipment identity |
| `equipment_type` | Pump, Motor, Compressor or Valve |
| `manufacturer` | Fictional label; empty means unverified/missing, never inferred |
| `criticality` | A = high, B = medium, C = low; fictional planning categorization |
| `installation_date` | Valid ISO date on or before reporting start for this full-year fleet cohort |
| `material_id` | Fictional item reference shared by compatible assets; no material dimension is modeled |
| `plant` | NORTH, EAST or SOUTH; all plants fictional |
| `data_quality_status` | Clean output only: accepted or needs_enrichment |
| `quarantine_reason` | Held output only: pipe-separated blocking rules; original values retained |

## Maintenance events

Grain: one `work_order_id`. Each corrective work order represents exactly one simulated failure. No multi-failure work order or work-order lifecycle is modeled.

| Field | Definition and control |
|---|---|
| `source_row` | Synthetic ingestion row identifier |
| `work_order_id` | Unique, nonempty event key; repeated keys are all held for review |
| `equipment_id` | Foreign key into the accepted asset master |
| `maintenance_date` | Valid date in the reporting window |
| `maintenance_type` | Planned or Corrective |
| `cost_eur` | Finite, nonnegative total synthetic event cost |
| `downtime_hours` | Finite, nonnegative event duration; not interval-based operational downtime |
| `failure_flag` | 1 for Corrective, 0 for Planned; consistency required |
| `quarantine_reason` | Held output only: blocking rules |

## Measures

Unless specified otherwise, numerators use accepted work orders and denominators use accepted assets. Every accepted asset is assumed exposed for the full reporting year. A missing manufacturer does not remove an asset or its work orders from the KPI scope.

| Measure | Definition | Interpretation |
|---|---|---|
| Asset count | Count of accepted unique equipment IDs | Includes assets with zero accepted work orders |
| Work-order count | Count of accepted unique work-order IDs | Held work orders excluded |
| Maintenance cost | Sum of accepted `cost_eur` | Accepted scope only; incomplete until holds reconcile |
| Corrective cost | Sum of cost where `failure_flag = 1` | No additional unobserved costs estimated |
| Corrective cost share | Corrective cost / total accepted cost × 100 | Undefined if total cost is zero |
| Failure count | Sum of `failure_flag` | One failure per corrective event by design |
| Cost per asset | Accepted cost / accepted assets in the selected fleet | Fleet mix matters for comparisons |
| Failures per 100 asset-years | Failures / accepted full-year assets × 100 | Repeated failures can make this greater than 100 |
| Mean corrective downtime | Sum of corrective event downtime / failures | Null for assets with no failure; proxy, not validated MTTR |
| Last maintenance date | Maximum accepted event date | Null if no accepted maintenance exists |
| Rows with any issue | Distinct `source_row` in the issue register per table | Do not sum rule counts: one row may fail several rules |
| Master acceptance rate | Accepted unique master rows / raw master rows | Denominator includes duplicates; not a pure completeness score |
| Manufacturer completeness | Accepted assets with nonempty manufacturer / accepted assets | Measures completeness only; not correctness |

Grouped SQL amounts round to two decimals. Cost totals reconcile within a cent using standard floating-point aggregation. A production finance pipeline should use integer minor units or a fixed-decimal database type.

`monthly_kpis.csv` summarizes work orders by event month. It is not an exposure-adjusted monthly failure rate. Full-year fleet measures should not be labeled monthly rates when a date slicer changes the numerator.
