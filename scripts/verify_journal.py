"""Vérifie que le rebalancement PAPER quotidien ALIMENTE bien `data/journal.db` (BLOC 4).

Ne dépend QUE de la librairie standard (sqlite3). À lancer SUR TON MAC, idéalement
après un run quotidien réel (`scripts/cron_live.sh`) :

  python3 scripts/verify_journal.py
  python3 scripts/verify_journal.py --max-age-days 4   # tolère un week-end

Contrôle deux plans :
  1. PLANIFICATION  — LaunchAgent `com.quant.live` chargé + fraîcheur du log `/tmp/quant_live.log`.
  2. JOURNALISATION — trades RÉELS (legacy=0) : count>0, cryptos BTC/ETH présents,
     timestamp récent, `features_snapshot` non vide (capture ML intacte).

Sortie : code 0 si tout passe, 1 si un contrôle BLOQUANT échoue, 2 si l'état est
UNCALIBRATED (aucun trade legacy=0 encore — attendu avant le 1er run réel). Aucun ordre.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "journal.db"
# ~/Library/Logs = emplacement persistant au reboot (macOS purge /tmp) ; /tmp = fallback
# pour un LaunchAgent installé avant le fix, ou pour Linux.
LIVE_LOGS = [Path.home() / "Library" / "Logs" / "quant_live.log", Path("/tmp/quant_live.log")]
LAUNCHD_LABEL = "com.quant.live"

OK, WARN, BAD, INFO = "  ✓", "  ⚠", "  ✗", "  ·"


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def check_schedule() -> bool:
    """LaunchAgent chargé + log récent. Non bloquant (info), mais on le signale."""
    print("PLANIFICATION (launchd)")
    ok = True
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10).stdout
        loaded = any(LAUNCHD_LABEL in ln for ln in out.splitlines())
    except Exception as e:  # noqa: BLE001
        print(f"{WARN} launchctl indisponible ({str(e)[:40]}) — vérif planif ignorée"); return True
    if loaded:
        print(f"{OK} LaunchAgent {LAUNCHD_LABEL} chargé (lun-ven 16h05)")
    else:
        print(f"{BAD} LaunchAgent {LAUNCHD_LABEL} NON chargé → `make live-cron-install`"); ok = False

    log = next((p for p in LIVE_LOGS if p.exists()), None)
    if log is not None:
        age_h = (time.time() - log.stat().st_mtime) / 3600.0
        tag = OK if age_h < 24 else WARN
        print(f"{tag} log {log} présent (dernière écriture il y a {age_h:.1f} h)")
    else:
        print(f"{INFO} log absent ({' / '.join(str(p) for p in LIVE_LOGS)}) — "
              f"le cron n'a pas encore tourné")
    return ok


def _assert_live_trades(conn, n_live: int, max_ts: str, max_age_days: float) -> bool:
    """Les 4 contrôles BLOQUANTS sur les trades réels (legacy=0). Retourne True si tout passe."""
    instruments = [r[0] for r in conn.execute(
        "SELECT DISTINCT instrument FROM trades WHERE legacy=0").fetchall()]
    ok = True
    print(f"{OK} count(legacy=0) = {n_live} > 0")                      # 1) count > 0

    up = " ".join(instruments).upper()                                # 2) cryptos BTC/ETH
    for want in ("BTC", "ETH"):
        if want in up:
            print(f"{OK} crypto {want} présent dans les instruments réels")
        else:
            print(f"{BAD} crypto {want} ABSENT (attendu via Alpaca crypto paper — ADR-0029)"); ok = False

    dt = _parse_iso(max_ts or "")                                     # 3) timestamp récent
    if dt is None:
        print(f"{BAD} entry_ts illisible ({max_ts!r})"); ok = False
    else:
        age_d = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        tag = OK if age_d <= max_age_days else BAD
        ok = ok and age_d <= max_age_days
        print(f"{tag} dernier entry_ts {max_ts} (il y a {age_d:.1f} j, seuil {max_age_days:.0f} j)")

    n_empty = conn.execute(                                           # 4) features_snapshot non vide
        "SELECT COUNT(*) FROM trades WHERE legacy=0 AND "
        "(features_snapshot IS NULL OR features_snapshot IN ('', '{}'))").fetchone()[0]
    if n_empty == 0:
        print(f"{OK} features_snapshot capturé pour les {n_live} trades réels")
    else:
        print(f"{BAD} {n_empty}/{n_live} trade(s) legacy=0 SANS features_snapshot — capture ML perdue"); ok = False

    print(f"\n{INFO} instruments réels : {', '.join(sorted(instruments))}")
    return ok


def check_journal(db: Path, max_age_days: float) -> int:
    """Retourne 0 (OK), 1 (échec bloquant) ou 2 (UNCALIBRATED : pas encore de trade réel)."""
    print(f"\nJOURNALISATION ({db})")
    if not db.exists():
        print(f"{BAD} base absente — aucun run n'a écrit de journal"); return 1
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        n_all = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        n_live, _n_instr, max_ts = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT instrument), MAX(entry_ts) "
            "FROM trades WHERE legacy=0").fetchone()
        print(f"{INFO} {n_all} trade(s) au total · {n_live} RÉEL(s) (legacy=0) · {n_all - n_live} importé(s) (legacy=1)")

        if n_live == 0:
            print(f"{WARN} UNCALIBRATED : aucun trade legacy=0 — le run quotidien n'a encore "
                  f"RIEN journalisé.\n       · Normal tant que le cron (lun-ven 16h05) n'a pas "
                  f"tourné depuis le déploiement\n         du journal de prod (P0-4 : run_live "
                  f"journalise ACHATS + round-trip des VENTES).\n       · Si un run de semaine "
                  f"est passé SANS rien écrire : soit aucun ordre envoyé (déjà\n         aligné), "
                  f"soit fill non exploitable — voir ~/Library/Logs/quant_live.log.")
            return 2

        return 0 if _assert_live_trades(conn, n_live, max_ts, max_age_days) else 1
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Vérifie l'alimentation de journal.db par le cron paper (BLOC 4)")
    ap.add_argument("--db", type=Path, default=Path(os.environ.get("QUANT_JOURNAL_DB", DEFAULT_DB)))
    ap.add_argument("--max-age-days", type=float, default=4.0,
                    help="âge max du dernier trade réel (défaut 4 j : tolère un week-end)")
    a = ap.parse_args()

    sched_ok = check_schedule()
    jrc = check_journal(a.db, a.max_age_days)

    print("\n" + "─" * 60)
    if jrc == 2:
        print("RÉSULTAT : UNCALIBRATED — en attente du 1er run quotidien réel qui journalise.")
        sys.exit(2)
    if jrc == 0 and sched_ok:
        print("RÉSULTAT : ✅ journal.db alimenté, cryptos présents, features capturées, cron actif.")
        sys.exit(0)
    print("RÉSULTAT : ❌ un contrôle bloquant a échoué (voir ci-dessus).")
    sys.exit(1)


if __name__ == "__main__":
    main()
