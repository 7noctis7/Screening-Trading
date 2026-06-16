"""Orchestrateur — planifie les jobs récurrents (nécessite APScheduler).

  python scripts/scheduler.py

Jobs :
  - rebuild_univers : MENSUEL (1er du mois, 02:00 UTC) → build --network + snapshot daté.
  - update_data     : QUOTIDIEN EOD (à brancher en P1 : ingestion delta → bronze/silver).

Alternative sans process long : cron.  Ex. mensuel :
  0 2 1 * *  cd /path/projet && python scripts/build_universe.py --network --force
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rebuild_universe() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_universe.py"),
                    "--network"], check=False)


def main() -> int:
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("APScheduler requis : uv pip install apscheduler"); return 1
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(rebuild_universe, CronTrigger(day=1, hour=2, minute=0),
                  id="rebuild_univers", name="Rebuild univers (mensuel)")
    print("Scheduler démarré — rebuild univers le 1er de chaque mois à 02:00 UTC.")
    sched.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
