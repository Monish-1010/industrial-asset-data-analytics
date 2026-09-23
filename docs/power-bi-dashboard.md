# Power BI implementation specification

The repository includes CSV tables and an exported SVG overview. It does not contain a `.pbix`; the specification below is the intended Power BI handoff and has not been validated in a running Power BI session.

## Import and relationships

Load `data/processed/assets_clean.csv` as **Assets** and `work_orders_clean.csv` as **WorkOrders**. Use Whole Number for `failure_flag`, Fixed Decimal Number for costs and duration, Date for date fields, and Text for keys. Keep manufacturer blanks visible as `Unverified` in a presentation column; do not replace the stored source value.

Create a **Calendar** table covering 2025-01-01 through 2025-12-31. Mark it as a date table. Create single-direction, one-to-many relationships:

```text
Assets[equipment_id]  1 ─── * WorkOrders[equipment_id]
Calendar[Date]        1 ─── * WorkOrders[maintenance_date]
```

Assets contains plant/type/criticality attributes, so plant and type slicers filter both fleet measures and maintenance facts. Do not join raw or quarantine records into this model: duplicate keys and unmatched references undermine the fact grain.

Load `data_quality_issues.csv`, raw CSVs and quarantine CSVs as separate, disconnected audit tables named **QualityIssues**, **RawAssets**, **RawWorkOrders**, **HeldAssets**, **HeldWorkOrders**. This preserves a clear distinction between accepted-fleet analysis and source-batch quality. The quality page describes the entire synthetic batch and should not respond to plant/date slicers unless an explicit audit dimension and relationship are designed.

## Core DAX measures

```dax
Accepted Assets = COUNTROWS(Assets)
Accepted Work Orders = COUNTROWS(WorkOrders)
Maintenance Cost EUR = SUM(WorkOrders[cost_eur])
Failures = SUM(WorkOrders[failure_flag])
Corrective Cost EUR =
    CALCULATE([Maintenance Cost EUR], WorkOrders[failure_flag] = 1)
Corrective Cost Share = DIVIDE([Corrective Cost EUR], [Maintenance Cost EUR])
Cost per Asset EUR = DIVIDE([Maintenance Cost EUR], [Accepted Assets])
Mean Corrective Downtime Hours =
    DIVIDE(
        CALCULATE(SUM(WorkOrders[downtime_hours]), WorkOrders[failure_flag] = 1),
        [Failures]
    )
Missing Manufacturer Assets =
    COUNTROWS(FILTER(Assets, ISBLANK(Assets[manufacturer]) || Assets[manufacturer] = ""))
Manufacturer Completeness =
    1 - DIVIDE([Missing Manufacturer Assets], [Accepted Assets])
Raw Asset Rows = COUNTROWS(RawAssets)
Held Asset Rows = COUNTROWS(HeldAssets)
Held Work Order Rows = COUNTROWS(HeldWorkOrders)
Asset Rows With Issues =
    CALCULATE(DISTINCTCOUNT(QualityIssues[source_row]), QualityIssues[table_name] = "assets")
```

Format cost share and completeness as percentages; these measures return fractions. SQL outputs with `_pct` suffix use a 0–100 scale and must not be formatted as fractional percentages without dividing by 100.

For the full-year failure-frequency measure, explicitly remove the date filter while retaining fleet filters:

```dax
Full-Year Failures per 100 Asset-Years =
    DIVIDE(
        CALCULATE([Failures], REMOVEFILTERS(Calendar)),
        [Accepted Assets]
    ) * 100
```

Label this measure **Full-year 2025** even when another chart uses a month selection. The fleet is assumed constant. A future model with commissioning/retirement dates needs explicit exposure calculations instead.

## Pages

| Page | Visuals | Decision supported |
|---|---|---|
| Fleet overview | Asset count, accepted cost, corrective share, full-year failure frequency; cost by plant; monthly cost trend | Where should a planner start a review? |
| Maintenance review | Equipment matrix with criticality, failures, cost, mean corrective downtime and last maintenance; plant/type/criticality filters | Which accepted assets show repeated corrective events? |
| Data quality | Raw/accepted/held counts; manufacturer completeness; findings by rule/disposition; issue-detail table | Which records need a steward and why? |

Use navy `#10243A`, teal `#087F8C`, gold `#E9B44C`, background `#F5F7FA`. Place **SYNTHETIC CASE STUDY** and **Accepted data only** in the overview subtitle. Gold indicates unresolved data quality, not a proven operational risk. Include tooltips with definitions and excluded-record counts.

## Reconciliation checklist

- Overview shows 176 accepted assets, 587 work orders, EUR 561,115.14 cost and 190 failures before filters.
- Corrective cost share rounds to 69.09%; mean corrective downtime rounds to 13.32 hours.
- Held counts are 13 asset rows and 17 event rows; raw counts are 189 and 604.
- Missing manufacturers: 11 accepted assets. Empty values are not presented as confirmed manufacturers.
- Asset matrix includes ten assets with no accepted work orders; show zeros for count/cost and blanks for mean repair duration.
- SQL plant totals reconcile to the overall cost within EUR 0.01. Test plant/type slicers and ensure audit totals remain visibly batch-scoped.
- Show clear units and whether a measure uses selected dates or the full calendar year. Do not label summed event downtime as availability.
