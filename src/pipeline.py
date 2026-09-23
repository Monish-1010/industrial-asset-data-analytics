"""Deterministic data generation, auditable cleaning, SQLite analysis and SVG reporting.

All names, events, prices and records are fictional. No operational company data
is used. Python 3.11+; standard library only.
"""
import csv
import json
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from html import escape
from pathlib import Path

SEED = 20260923
START, END = date(2025, 1, 1), date(2025, 12, 31)
ASSET_FIELDS = ["source_row", "equipment_id", "functional_location", "equipment_type", "manufacturer", "criticality", "installation_date", "material_id", "plant"]
WO_FIELDS = ["source_row", "work_order_id", "equipment_id", "maintenance_date", "maintenance_type", "cost_eur", "downtime_hours", "failure_flag"]
ISSUE_FIELDS = ["table_name", "source_row", "record_key", "rule", "severity", "disposition", "detail"]
ASSET_CLEAN_FIELDS = ASSET_FIELDS[1:] + ["data_quality_status"]
WO_CLEAN_FIELDS = WO_FIELDS[1:]


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_data():
    """Build 180 assets and 600 maintenance events, then inject known defects."""
    rng = random.Random(SEED)
    assets = []
    types = ["Pump", "Motor", "Compressor", "Valve"]
    for n in range(1, 181):
        plant = ["NORTH", "EAST", "SOUTH"][(n - 1) % 3]
        assets.append({
            "source_row": f"A{n:04d}", "equipment_id": f"EQ-{n:04d}",
            "functional_location": f"{plant}-UNIT-{(n - 1) % 4 + 1:02d}",
            "equipment_type": types[(n - 1) % 4],
            "manufacturer": ["Fictional Atlas", "Fictional Meridian", "Fictional Cedar"][n % 3],
            "criticality": rng.choices(["A", "B", "C"], weights=[2, 5, 3])[0],
            "installation_date": (date(2013, 1, 1) + timedelta(days=rng.randrange(4200))).isoformat(),
            "material_id": f"MAT-{(n - 1) % 12 + 1:03d}", "plant": plant,
        })
    events = []
    for n in range(1, 601):
        asset = rng.choice(assets)
        # A deliberate scenario assumption, not a fitted empirical relationship.
        probability = 0.48 if asset["equipment_type"] == "Compressor" else 0.25
        failure = int(rng.random() < probability)
        events.append({
            "source_row": f"W{n:04d}", "work_order_id": f"WO-{n:05d}",
            "equipment_id": asset["equipment_id"],
            "maintenance_date": (START + timedelta(days=rng.randrange(365))).isoformat(),
            "maintenance_type": "Corrective" if failure else "Planned",
            "cost_eur": f"{rng.uniform(600, 3500) if failure else rng.uniform(100, 750):.2f}",
            "downtime_hours": f"{rng.uniform(2, 24) if failure else rng.uniform(0.5, 4):.2f}",
            "failure_flag": str(failure),
        })
    for n in range(0, 180, 11):
        assets[n]["equipment_id"] = f" {assets[n]['equipment_id'].lower()} "
    for n in range(0, 180, 13):
        assets[n]["equipment_type"] = " " + assets[n]["equipment_type"].upper() + " "
    for n in range(3, 180, 17):
        assets[n]["manufacturer"] = ""
    for n in range(5, 180, 19):
        assets[n]["installation_date"] = assets[n]["installation_date"].replace("-", "/")
    assets[4]["criticality"] = "URGENT"
    assets[5]["installation_date"] = "not-recorded"
    for n in range(4):
        clone = dict(assets[20 + n])
        clone["source_row"] = f"A{181 + n:04d}"
        assets.append(clone)
    for n in range(2):
        clone = dict(assets[30 + n])
        clone["source_row"] = f"A{185 + n:04d}"
        clone["criticality"] = "C" if clone["criticality"] != "C" else "A"
        assets.append(clone)
    for n in range(3):
        clone = dict(assets[40 + n])
        clone["source_row"] = f"A{187 + n:04d}"
        clone["equipment_id"] = ""
        assets.append(clone)
    defects = [
        ("cost_eur", "-900.00"),
        ("maintenance_date", "2025-02-30"),
        ("equipment_id", "EQ-9999"),
        ("failure_flag", "2"),
    ]
    for n, (field, value) in enumerate(defects, start=601):
        clone = dict(events[n - 601])
        clone.update(source_row=f"W{n:04d}", work_order_id=f"WO-{n:05d}")
        clone[field] = value
        events.append(clone)
    return assets, events


def add_issue(issues, table, row, key, rule, severity, disposition, detail):
    issues.append(dict(zip(ISSUE_FIELDS, [table, row, key, rule, severity, disposition, detail])))


def canonical_asset(raw):
    value = {key: raw[key].strip() for key in ASSET_FIELDS[1:]}
    for key in ["equipment_id", "functional_location", "criticality", "material_id", "plant"]:
        value[key] = value[key].upper()
    value["equipment_type"] = value["equipment_type"].title()
    value["installation_date"] = value["installation_date"].replace("/", "-")
    return value


def clean_assets(raw_rows):
    issues, clean, quarantine = [], [], []
    groups = defaultdict(list)
    for row in raw_rows:
        groups[canonical_asset(row)["equipment_id"]].append(row)
    for raw in raw_rows:
        row = canonical_asset(raw)
        key, source = row["equipment_id"], raw["source_row"]
        reasons = []
        changed = [field for field in ASSET_FIELDS[1:] if row[field] != raw[field]]
        if changed:
            add_issue(issues, "assets", source, key, "format_standardized", "info", "auto_corrected", ", ".join(changed))
        if not key or not (len(key) == 7 and key.startswith("EQ-") and key[3:].isdigit()):
            reasons.append(("invalid_equipment_id", "A stable EQ-0000 key is required; do not infer identity."))
        elif len(groups[key]) > 1:
            fingerprints = {tuple(canonical_asset(r).values()) for r in groups[key]}
            if len(fingerprints) > 1:
                reasons.append(("conflicting_duplicate", "All versions held for master-data steward review."))
            elif raw is not groups[key][0]:
                reasons.append(("exact_duplicate", "Lowest source row retained after canonical comparison."))
        for field, allowed in [("equipment_type", {"Pump", "Motor", "Compressor", "Valve"}), ("criticality", {"A", "B", "C"}), ("plant", {"NORTH", "EAST", "SOUTH"})]:
            if row[field] not in allowed:
                reasons.append((f"invalid_{field}", f"Value outside controlled domain: {row[field]}"))
        try:
            installed = date.fromisoformat(row["installation_date"])
            if installed > START:
                raise ValueError("outside supported fleet cohort")
        except ValueError:
            reasons.append(("invalid_installation_date", "A valid ISO date on or before 2025-01-01 is required."))
        if not row["manufacturer"]:
            add_issue(issues, "assets", source, key, "missing_manufacturer", "warning", "needs_enrichment", "Leave missing; steward must supply verified manufacturer.")
        if reasons:
            for rule, detail in reasons:
                disposition = "duplicate_removed" if rule == "exact_duplicate" else "quarantined"
                add_issue(issues, "assets", source, key, rule, "error", disposition, detail)
            quarantine.append({**raw, "quarantine_reason": "|".join(r[0] for r in reasons)})
        else:
            row["data_quality_status"] = "needs_enrichment" if not row["manufacturer"] else "accepted"
            clean.append(row)
    return clean, quarantine, issues


def clean_work_orders(raw_rows, valid_assets):
    issues, clean, quarantine = [], [], []
    counts = Counter(r["work_order_id"].strip() for r in raw_rows)
    for raw in raw_rows:
        row = {field: raw[field].strip() for field in WO_FIELDS[1:]}
        key, source = row["work_order_id"], raw["source_row"]
        reasons = []
        if not key or counts[key] > 1:
            reasons.append(("invalid_work_order_key", "Missing or duplicated key; all versions held."))
        if row["equipment_id"] not in valid_assets:
            reasons.append(("orphan_equipment_id", "Asset is absent from accepted master; event excluded from KPIs."))
        try:
            event_date = date.fromisoformat(row["maintenance_date"])
            if not START <= event_date <= END:
                raise ValueError("outside reporting window")
        except ValueError:
            reasons.append(("invalid_maintenance_date", "A valid date in the 2025 reporting window is required."))
        for field in ["cost_eur", "downtime_hours"]:
            try:
                value = float(row[field])
                if not (0 <= value < float("inf")):
                    raise ValueError("invalid amount")
                row[field] = f"{value:.2f}"
            except ValueError:
                reasons.append((f"invalid_{field}", "Value must be finite and nonnegative."))
        if row["maintenance_type"] not in {"Corrective", "Planned"}:
            reasons.append(("invalid_maintenance_type", "Expected Corrective or Planned."))
        if row["failure_flag"] not in {"0", "1"} or (row["failure_flag"] == "1") != (row["maintenance_type"] == "Corrective"):
            reasons.append(("invalid_failure_flag", "This scenario defines one failure per corrective event and none per planned event."))
        if reasons:
            for rule, detail in reasons:
                add_issue(issues, "work_orders", source, key, rule, "error", "quarantined", detail)
            quarantine.append({**raw, "quarantine_reason": "|".join(r[0] for r in reasons)})
        else:
            clean.append(row)
    return clean, quarantine, issues


def execute_sql(assets, events, output):
    output.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(output / "analytics.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parents[1] / "sql" / "analysis.sql").read_text(encoding="utf-8"))
    conn.executemany("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?)", [tuple(r[f] for f in ASSET_CLEAN_FIELDS) for r in assets])
    conn.executemany("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?)", [tuple(r[f] for f in WO_CLEAN_FIELDS) for r in events])
    results = {}
    for name, order in [("asset_kpis", "failure_count DESC, maintenance_cost_eur DESC, equipment_id"), ("plant_kpis", "maintenance_cost_eur DESC, plant"), ("type_kpis", "maintenance_cost_eur DESC, equipment_type"), ("monthly_kpis", "month")]:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {name} ORDER BY {order}")]
        write_csv(output / f"{name}.csv", rows)
        results[name] = rows
    conn.commit()
    conn.close()
    return results


def svg_report(path, metrics, plant_rows):
    navy, teal, gold, bg = "#10243A", "#087F8C", "#E9B44C", "#F5F7FA"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="710" viewBox="0 0 1200 710" role="img" aria-labelledby="title desc"><title id="title">Synthetic industrial asset analytics</title><desc id="desc">Accepted asset and maintenance totals, cost by plant, and data quality exclusions. All values are simulated.</desc><rect width="1200" height="710" fill="{bg}"/>']
    def text(x, y, label, size=18, fill=navy, weight="400"):
        parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(str(label))}</text>')
    text(48, 51, "EAM / MASTER DATA / MAINTENANCE", 15, teal, "700")
    text(48, 95, "Industrial asset analytics", 36, navy, "700")
    text(48, 126, "Synthetic case study · Calendar year 2025 · EUR", 18)
    cards = [("Accepted assets", metrics["accepted_assets"]), ("Accepted work orders", metrics["accepted_work_orders"]), ("Maintenance cost", f"EUR {metrics['maintenance_cost_eur']:,.0f}"), ("Corrective cost share", f"{metrics['corrective_cost_share_pct']:.1f}%")]
    for i, (label, value) in enumerate(cards):
        x = 48 + i * 280
        parts.append(f'<rect x="{x}" y="163" width="264" height="108" rx="10" fill="white"/>')
        text(x + 18, 195, label, 17)
        text(x + 18, 241, value, 29, teal, "700")
    text(48, 322, "Maintenance cost by plant", 23, navy, "700")
    maximum = max(r["maintenance_cost_eur"] for r in plant_rows)
    for i, row in enumerate(plant_rows):
        y = 350 + i * 62
        width = round(row["maintenance_cost_eur"] / maximum * 640)
        text(48, y + 23, row["plant"], 16)
        parts.append(f'<rect x="135" y="{y}" width="{width}" height="30" rx="4" fill="{teal}"/>')
        text(145 + width, y + 22, f"EUR {row['maintenance_cost_eur']:,.0f}", 16)
    parts.append(f'<rect x="935" y="309" width="215" height="229" rx="10" fill="{navy}"/>')
    text(952, 345, "Data quality holds", 20, "white", "700")
    text(952, 390, f"{metrics['held_asset_rows']} asset rows", 24, gold, "700")
    text(952, 422, f"{metrics['held_work_order_rows']} event rows", 24, gold, "700")
    text(952, 463, "Excluded from KPI scope", 15, "white")
    text(952, 494, "Every hold is traceable", 15, "white")
    text(48, 594, "What this demonstrates", 21, navy, "700")
    text(48, 629, "Canonical keys → quarantine and stewardship → SQL KPIs → business review", 19)
    text(48, 673, "Illustrative outputs only. No company data, validated savings or operational recommendations.", 16)
    parts.append("</svg>")
    path.write_text("".join(parts), encoding="utf-8")


def run_pipeline(root):
    root = Path(root)
    for folder in ["data/raw", "data/processed", "results", "images"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    raw_assets, raw_events = generate_data()
    write_csv(root / "data/raw/assets.csv", raw_assets, ASSET_FIELDS)
    write_csv(root / "data/raw/work_orders.csv", raw_events, WO_FIELDS)
    assets, held_assets, asset_issues = clean_assets(raw_assets)
    events, held_events, event_issues = clean_work_orders(raw_events, {r["equipment_id"] for r in assets})
    issues = asset_issues + event_issues
    write_csv(root / "data/processed/assets_clean.csv", assets, ASSET_CLEAN_FIELDS)
    write_csv(root / "data/processed/work_orders_clean.csv", events, WO_CLEAN_FIELDS)
    write_csv(root / "data/processed/assets_quarantine.csv", held_assets, ASSET_FIELDS + ["quarantine_reason"])
    write_csv(root / "data/processed/work_orders_quarantine.csv", held_events, WO_FIELDS + ["quarantine_reason"])
    write_csv(root / "results/data_quality_issues.csv", issues, ISSUE_FIELDS)
    counts = Counter((r["table_name"], r["rule"], r["disposition"]) for r in issues)
    write_csv(root / "results/data_quality_summary.csv", [dict(table_name=k[0], rule=k[1], disposition=k[2], issue_count=v) for k, v in sorted(counts.items())])
    results = execute_sql(assets, events, root / "results")
    total_cost = round(sum(float(r["cost_eur"]) for r in events), 2)
    corrective_cost = sum(float(r["cost_eur"]) for r in events if r["failure_flag"] == "1")
    failures = sum(int(r["failure_flag"]) for r in events)
    repair_hours = sum(float(r["downtime_hours"]) for r in events if r["failure_flag"] == "1")
    metrics = {
        "seed": SEED, "reporting_start": START.isoformat(), "reporting_end": END.isoformat(),
        "raw_asset_rows": len(raw_assets), "accepted_assets": len(assets), "held_asset_rows": len(held_assets),
        "raw_work_order_rows": len(raw_events), "accepted_work_orders": len(events), "held_work_order_rows": len(held_events),
        "asset_rows_with_any_issue": len({r["source_row"] for r in asset_issues}),
        "accepted_assets_missing_manufacturer": sum(not r["manufacturer"] for r in assets),
        "maintenance_cost_eur": total_cost, "failure_count": failures,
        "corrective_cost_share_pct": round(corrective_cost / total_cost * 100, 2),
        "mean_corrective_downtime_hours": round(repair_hours / failures, 2) if failures else None,
        "failures_per_100_asset_years": round(failures / len(assets) * 100, 2),
        "assets_without_accepted_work_orders": sum(r["work_order_count"] == 0 for r in results["asset_kpis"]),
    }
    (root / "results/summary.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    svg_report(root / "images/portfolio-overview.svg", metrics, results["plant_kpis"])
    top = results["plant_kpis"][0]
    top_type = results["type_kpis"][0]
    report = f"""# Findings from the synthetic scenario

Generated by `python run.py`; reporting window: 1 January–31 December 2025.

- Accepted scope: **{len(assets)} assets and {len(events)} work orders**. The pipeline holds {len(held_assets)} master rows (including exact duplicate removals) and {len(held_events)} event rows outside KPI calculations.
- Accepted maintenance cost is **EUR {total_cost:,.2f}**. Corrective work contributes **{metrics['corrective_cost_share_pct']:.2f}%** of cost across {failures} simulated failures.
- **{top['plant']}** has the highest total cost, **EUR {top['maintenance_cost_eur']:,.2f}**, and **EUR {top['cost_per_asset_eur']:,.2f} per accepted asset**. Review cost per asset and fleet mix together before proposing an intervention; total spending alone is not performance.
- **{top_type['equipment_type']}** has the highest total cost by equipment type. The generator deliberately assigns compressors a higher corrective-event probability. This is a scenario assumption, not a discovery about real machinery.
- **{metrics['accepted_assets_missing_manufacturer']} accepted assets** still need manufacturer enrichment. Missing values remain visible; no manufacturer is guessed.
- Mean corrective downtime is **{metrics['mean_corrective_downtime_hours']:.2f} hours per failure**. This is an event-level repair-duration proxy, not measured operational availability or a validated MTTR benchmark.

## Proposed review actions

1. A master-data steward should resolve conflicting asset keys and invalid criticality/date values using an approved source. Every excluded row is retained with a reason; publication of a corrected master requires review.
2. A maintenance planner could review repeated corrective events in `asset_kpis.csv`, starting with high-criticality assets. Validate fault codes, actual operating exposure and maintenance history before changing a plan.
3. An analyst should reconcile held work orders and related costs before presenting a financial total as complete. Accepted-only spending is not the total cost of the raw source.
4. Track manufacturer completeness, unique stable keys and referential integrity as separate measures. A single combined quality score can hide different business risks.

## Limits

All results are simulated. Equipment labels, frequencies, costs and durations are chosen for demonstration. All accepted assets are assumed in scope for the full calendar year; there are no meter readings, labor calendars, spare-parts lead times, overlapping-downtime controls or failure severity data. No real-world savings, impact, causality, plant ranking or deployment is claimed.
"""
    (root / "results/business_insights.md").write_text(report, encoding="utf-8")
    return metrics
