-- Executed by run.py before inserts. Views are evaluated after validated CSVs load.
-- Rebuild explicitly; no external database or credentials are used.
PRAGMA foreign_keys = ON;
DROP VIEW IF EXISTS monthly_kpis;
DROP VIEW IF EXISTS type_kpis;
DROP VIEW IF EXISTS plant_kpis;
DROP VIEW IF EXISTS asset_kpis;
DROP TABLE IF EXISTS work_orders;
DROP TABLE IF EXISTS assets;

CREATE TABLE assets (
    equipment_id TEXT PRIMARY KEY,
    functional_location TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    manufacturer TEXT NOT NULL,
    criticality TEXT NOT NULL CHECK (criticality IN ('A','B','C')),
    installation_date TEXT NOT NULL,
    material_id TEXT NOT NULL,
    plant TEXT NOT NULL,
    data_quality_status TEXT NOT NULL
);
CREATE TABLE work_orders (
    work_order_id TEXT PRIMARY KEY,
    equipment_id TEXT NOT NULL REFERENCES assets(equipment_id),
    maintenance_date TEXT NOT NULL,
    maintenance_type TEXT NOT NULL CHECK (maintenance_type IN ('Planned','Corrective')),
    cost_eur REAL NOT NULL CHECK (cost_eur >= 0),
    downtime_hours REAL NOT NULL CHECK (downtime_hours >= 0),
    failure_flag INTEGER NOT NULL CHECK (failure_flag IN (0,1))
);

-- Left join preserves the denominator and assets with no accepted events.
CREATE VIEW asset_kpis AS
SELECT a.equipment_id, a.plant, a.equipment_type, a.criticality,
       COUNT(w.work_order_id) AS work_order_count,
       COALESCE(SUM(w.failure_flag), 0) AS failure_count,
       ROUND(COALESCE(SUM(w.cost_eur), 0), 2) AS maintenance_cost_eur,
       ROUND(COALESCE(SUM(CASE WHEN w.failure_flag=1 THEN w.cost_eur ELSE 0 END), 0), 2) AS corrective_cost_eur,
       ROUND(COALESCE(SUM(w.downtime_hours), 0), 2) AS downtime_hours,
       ROUND(SUM(CASE WHEN w.failure_flag=1 THEN w.downtime_hours ELSE 0 END)
             / NULLIF(SUM(w.failure_flag), 0), 2) AS mean_corrective_downtime_hours,
       MAX(w.maintenance_date) AS last_maintenance_date
FROM assets a LEFT JOIN work_orders w ON a.equipment_id=w.equipment_id
GROUP BY a.equipment_id, a.plant, a.equipment_type, a.criticality;

CREATE VIEW plant_kpis AS
SELECT plant, COUNT(*) AS asset_count, SUM(work_order_count) AS work_order_count,
       SUM(failure_count) AS failure_count,
       ROUND(SUM(maintenance_cost_eur),2) AS maintenance_cost_eur,
       ROUND(SUM(corrective_cost_eur),2) AS corrective_cost_eur,
       ROUND(SUM(maintenance_cost_eur)/COUNT(*),2) AS cost_per_asset_eur,
       ROUND(100.0*SUM(failure_count)/COUNT(*),2) AS failures_per_100_asset_years,
       ROUND(100.0*SUM(corrective_cost_eur)/NULLIF(SUM(maintenance_cost_eur),0),2) AS corrective_cost_share_pct
FROM asset_kpis GROUP BY plant;

CREATE VIEW type_kpis AS
SELECT equipment_type, COUNT(*) AS asset_count, SUM(work_order_count) AS work_order_count,
       SUM(failure_count) AS failure_count,
       ROUND(SUM(maintenance_cost_eur),2) AS maintenance_cost_eur,
       ROUND(SUM(maintenance_cost_eur)/COUNT(*),2) AS cost_per_asset_eur,
       ROUND(100.0*SUM(failure_count)/COUNT(*),2) AS failures_per_100_asset_years
FROM asset_kpis GROUP BY equipment_type;

CREATE VIEW monthly_kpis AS
SELECT SUBSTR(maintenance_date,1,7) AS month, COUNT(*) AS work_order_count,
       SUM(failure_flag) AS failure_count,
       ROUND(SUM(cost_eur),2) AS maintenance_cost_eur,
       ROUND(SUM(CASE WHEN failure_flag=1 THEN cost_eur ELSE 0 END),2) AS corrective_cost_eur
FROM work_orders GROUP BY SUBSTR(maintenance_date,1,7);
