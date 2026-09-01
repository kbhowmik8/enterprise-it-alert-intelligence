"""Generate two demo alert workbooks (previous week / current week) for local testing.

Headers deliberately use ServiceNow-style aliases so the column normalizer in
analysis_engine.py is exercised too.
"""
import random
from datetime import datetime, timedelta

import pandas as pd

SEED = 42
OUT_PREV = "alerts_previous_week.xlsx"
OUT_CUR = "alerts_current_week.xlsx"

SEVERITIES = ["P1 - Critical", "P2 - High", "P3 - Moderate", "P4 - Low"]
CRITICALITIES = ["Business Critical", "High", "Medium", "Low"]
GROUPS = [
    "Network Operations",
    "Database Administration",
    "Windows Server Support",
    "Linux Platform Support",
    "Application Support - SAP",
    "Storage & Backup",
    "Cloud Platform - Azure",
]
CONFIG_ITEMS = [
    "PRD-SQL-CLUSTER-01",
    "PRD-WEB-APP-04",
    "CORE-SWITCH-DC1",
    "PRD-SAP-ECC-02",
    "BACKUP-NETAPP-01",
    "AZ-AKS-PROD-EU",
    "PRD-EXCHANGE-03",
    "VPN-GATEWAY-02",
]
# (short description, work note) pairs — repeated across weeks so the forecast
# has recurring signatures to score.
INCIDENTS = [
    ("CPU utilization above threshold on database node",
     "Long running query identified, index rebuild scheduled"),
    ("Disk space usage exceeded 90 percent on volume",
     "Archived old logs and extended LUN by 100GB"),
    ("Network latency spike detected between datacenters",
     "Carrier reported fibre maintenance, monitoring continues"),
    ("Backup job failed with media error",
     "Tape library cleaned and backup rerun successfully"),
    ("SAP batch job cancelled due to memory allocation failure",
     "Increased extended memory parameter and restarted job"),
    ("Web application response time degraded",
     "Connection pool exhausted, pool size increased"),
    ("Certificate expiring within seven days on gateway",
     "Renewal request raised with PKI team"),
    ("Cluster node unresponsive to heartbeat probe",
     "Node fenced and rejoined cluster after reboot"),
    ("Replication lag exceeded threshold on secondary",
     "Network throttle removed, replication caught up"),
    ("Authentication failures spike on VPN gateway",
     "Brute force attempt blocked at firewall, IPs blacklisted"),
    ("Memory leak suspected in application worker process",
     "Worker recycled, vendor case opened for permanent fix"),
    ("Scheduled patching caused unexpected service restart",
     "Service set to automatic delayed start, verified healthy"),
]


def build_week(rng: random.Random, start: datetime, n_rows: int, id_prefix: str) -> pd.DataFrame:
    rows = []
    for i in range(n_rows):
        desc, note = rng.choice(INCIDENTS)
        severity = rng.choices(SEVERITIES, weights=[1, 3, 5, 3])[0]
        created = start + timedelta(
            days=rng.randint(0, 6), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        # Higher severity gets resolved faster.
        max_hours = {"P1 - Critical": 6, "P2 - High": 24, "P3 - Moderate": 72}.get(severity, 120)
        updated = created + timedelta(hours=round(rng.uniform(0.25, max_hours), 2))
        rows.append(
            {
                "number": f"{id_prefix}{100000 + i}",
                "priority": severity,
                "impact": rng.choices(CRITICALITIES, weights=[1, 3, 5, 3])[0],
                "assignment group": rng.choice(GROUPS),
                "cmdb_ci": rng.choice(CONFIG_ITEMS),
                "opened_at": created,
                "sys_updated_on": updated,
                "reopen_count": rng.choices([0, 1, 2], weights=[85, 12, 3])[0],
                "short_description": desc,
                "work notes": note,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    rng = random.Random(SEED)
    prev_start = datetime(2025, 8, 11)
    prev = build_week(rng, prev_start, 180, "ALRT")
    cur = build_week(rng, prev_start + timedelta(days=7), 215, "ALRT")

    prev.to_excel(OUT_PREV, index=False, engine="openpyxl")
    cur.to_excel(OUT_CUR, index=False, engine="openpyxl")
    print(f"Created {OUT_PREV} ({len(prev)} rows)")
    print(f"Created {OUT_CUR} ({len(cur)} rows)")


if __name__ == "__main__":
    main()
