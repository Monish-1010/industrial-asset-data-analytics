# Quality rules and resolution workflow

The demonstration uses a synthetic batch source. It keeps original data, canonical accepted data and excluded data separately so a reviewer can trace every rule outcome.

## Decisions

| Rule | Handling | Reason |
|---|---|---|
| Known whitespace/case/date separator variation | Standardize and log `auto_corrected` | Deterministic representation change, no new business fact |
| Canonically identical asset duplicate | Keep first source row; retain extra row in quarantine as `duplicate_removed` | Prevent duplicated joins without losing evidence |
| Conflicting duplicate equipment ID | Hold all versions | No trusted timestamp/source authority exists to choose a winner |
| Missing or malformed equipment ID | Hold | Similar names or locations do not prove identity |
| Unknown criticality, type or plant | Hold | Requires an approved controlled-domain value |
| Invalid installation date | Hold | Full-year exposure assumption would be unsupported |
| Missing manufacturer | Accept with `needs_enrichment` | Does not invalidate identity or maintenance linkage; incompleteness remains visible |
| Work order references an unaccepted asset | Hold event | No trustworthy dimension row exists |
| Invalid event date, numeric value or failure flag | Hold event | Avoid invalid financial/duration totals and inconsistent categories |
| Duplicated or missing work-order key | Hold all versions | No event-level merge authority is available |

The code validates keys, domains, dates, event amounts and linkage. It does **not** verify that a manufacturer is factually correct, that a functional location matches physical installation, or that a material is technically compatible. Those require an authoritative reference and a steward.

## Register and reconciliation

`results/data_quality_issues.csv` has one row per rule finding with table, source row, key, severity, disposition and explanation. A record can appear more than once. `data_quality_summary.csv` counts findings by rule; it is not a count of unique bad records.

For each source table, the pipeline partitions records exactly once:

```text
raw asset rows = accepted unique master rows + held master rows
raw event rows = accepted work orders + held event rows
```

All held rows preserve source values and reasons. A missing manufacturer warning may coexist with a blocking issue; dashboards should evaluate final disposition from the accepted/quarantine tables, not infer it from an isolated warning.

## Proposed operational workflow

1. **Assign:** master-data steward owns asset identity/domain issues; maintenance planner owns event corrections. These are proposed roles, not real staff assignments.
2. **Investigate:** locate the authoritative asset record, installation evidence or work order. Do not use this synthetic dataset to infer real values.
3. **Record:** capture original value, proposed value, evidence, reviewer and decision date in a controlled correction log.
4. **Approve:** steward approves the corrected business fact; analyst reruns validation and reconciles accepted/held counts and spending.
5. **Publish:** release the accepted snapshot with reporting scope, remaining holds and limitations. Resolve causes in the source system rather than accumulating spreadsheet patches.

This repository demonstrates steps 1 and 2 as a triage output and implements deterministic technical fixes. It does not automatically close human-review cases or fabricate approved corrections. `run.py` always regenerates the original synthetic scenario, so manual edits to generated CSVs are not a correction mechanism.
