import csv
import tempfile
import unittest
from pathlib import Path

from src.pipeline import clean_assets, clean_work_orders, execute_sql, generate_data, run_pipeline


class AssetQualityTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.events = generate_data()

    def test_conflicts_hold_all_versions_and_do_not_guess(self):
        clean, held, issues = clean_assets(self.raw)
        keys = {r["equipment_id"] for r in clean}
        self.assertNotIn("EQ-0031", keys)
        self.assertNotIn("EQ-0032", keys)
        self.assertEqual(sum("conflicting_duplicate" in r["quarantine_reason"] for r in held), 4)
        self.assertEqual(sum(i["disposition"] == "duplicate_removed" for i in issues), 4)
        self.assertEqual(len(clean) + len(held), len(self.raw))

    def test_missing_identity_is_held_but_manufacturer_is_not_invented(self):
        clean, held, _ = clean_assets(self.raw)
        self.assertEqual(sum(not r["equipment_id"] for r in held), 3)
        incomplete = [r for r in clean if not r["manufacturer"]]
        self.assertEqual(len(incomplete), 11)
        self.assertTrue(all(r["data_quality_status"] == "needs_enrichment" for r in incomplete))
        self.assertTrue(all(r["equipment_id"].startswith("EQ-") for r in clean))

    def test_work_order_rejects_unknown_reference_negative_and_nonfinite_amounts(self):
        clean, _, _ = clean_assets(self.raw)
        keys = {r["equipment_id"] for r in clean}
        event = next(dict(r) for r in self.events if r["equipment_id"] in keys)
        for field, value, expected in [
            ("equipment_id", "EQ-9999", "orphan_equipment_id"),
            ("cost_eur", "-1", "invalid_cost_eur"),
            ("cost_eur", "NaN", "invalid_cost_eur"),
            ("downtime_hours", "inf", "invalid_downtime_hours"),
            ("maintenance_date", "2025-02-30", "invalid_maintenance_date"),
        ]:
            with self.subTest(field=field, value=value):
                accepted, held, _ = clean_work_orders([{**event, field: value}], keys)
                self.assertEqual(accepted, [])
                self.assertIn(expected, held[0]["quarantine_reason"])

    def test_duplicate_work_order_keys_hold_every_version(self):
        clean, _, _ = clean_assets(self.raw)
        keys = {r["equipment_id"] for r in clean}
        event = next(dict(r) for r in self.events if r["equipment_id"] in keys)
        accepted, held, _ = clean_work_orders([event, {**event, "source_row": "duplicate"}], keys)
        self.assertEqual(len(held), 2)
        self.assertEqual(accepted, [])


class AnalyticsTests(unittest.TestCase):
    def test_left_join_keeps_zero_event_assets_and_undefined_repair_mean(self):
        assets, _, _ = clean_assets(generate_data()[0])
        with tempfile.TemporaryDirectory() as directory:
            results = execute_sql([assets[0]], [], Path(directory))
        row = results["asset_kpis"][0]
        self.assertEqual(row["work_order_count"], 0)
        self.assertEqual(row["maintenance_cost_eur"], 0)
        self.assertIsNone(row["mean_corrective_downtime_hours"])
        self.assertEqual(results["plant_kpis"][0]["asset_count"], 1)

    def test_financial_and_record_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = run_pipeline(root)
            def read(name):
                with (root / name).open(newline="", encoding="utf-8") as handle:
                    return list(csv.DictReader(handle))
            accepted = read("data/processed/work_orders_clean.csv")
            plants = read("results/plant_kpis.csv")
            self.assertEqual(summary["raw_asset_rows"], summary["accepted_assets"] + summary["held_asset_rows"])
            self.assertEqual(summary["raw_work_order_rows"], summary["accepted_work_orders"] + summary["held_work_order_rows"])
            self.assertAlmostEqual(sum(float(r["cost_eur"]) for r in accepted), summary["maintenance_cost_eur"], places=2)
            self.assertAlmostEqual(sum(float(r["maintenance_cost_eur"]) for r in plants), summary["maintenance_cost_eur"], places=2)
            self.assertEqual(sum(int(r["asset_count"]) for r in plants), summary["accepted_assets"])
            self.assertEqual(summary["assets_without_accepted_work_orders"], 10)

    def test_all_portable_outputs_are_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            run_pipeline(Path(first))
            run_pipeline(Path(second))
            for path in Path(first).rglob("*"):
                if path.is_file() and path.suffix != ".sqlite":
                    relative = path.relative_to(first)
                    with self.subTest(file=str(relative)):
                        self.assertEqual(path.read_bytes(), (Path(second) / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()
