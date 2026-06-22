#!/usr/bin/env python3
"""Pousse les KPIs quotidiens du portefeuille vers Supabase (Postgres free tier) — historique
perf consultable de partout (#7). stdlib pure (urllib + PostgREST), zéro dépendance ajoutée.

Pré-requis : créer un projet Supabase, une table `daily_kpis` (SQL fourni dans le README de la
commande), et mettre SUPABASE_URL + SUPABASE_KEY dans .env (clé `service_role` ou `anon` selon RLS).

  python scripts/kpi_to_supabase.py            # lit le snapshot du jour → upsert d'une ligne
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Champs numériques que l'on archive (uniquement ceux présents → schéma tolérant).
_FIELDS = ("total_return", "cagr", "sharpe", "sortino", "calmar", "max_drawdown",
           "win_rate", "profit_factor", "expectancy", "p_ruin")


def build_row(metrics: dict, extra: dict | None = None, date: str | None = None) -> dict:
    """Construit la ligne KPI (date + champs numériques présents, arrondis). Pur/testable."""
    src = {**(metrics or {}), **(extra or {})}
    row = {"date": date or datetime.now(timezone.utc).date().isoformat()}
    for k in _FIELDS:
        v = src.get(k)
        if isinstance(v, (int, float)) and v == v:        # ignore None et NaN
            row[k] = round(float(v), 6)
    return row


def kpis_from_snapshot() -> dict:
    from apps.api import main as M
    M._snap()
    d = M.dashboard()
    extra = {}
    try:                                                   # p_ruin (Monte-Carlo) si exposé
        extra["p_ruin"] = (M.portfolio() or {}).get("monte_carlo", {}).get("p_ruin")
    except Exception:  # noqa: BLE001
        pass
    return build_row(d.get("metrics", {}) or {}, extra)


def push(row: dict, url: str, key: str, table: str = "daily_kpis") -> int:
    """Upsert (merge sur la PK `date`) via PostgREST. Renvoie le code HTTP."""
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}", data=json.dumps(row).encode(), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — endpoint Supabase de l'utilisateur
        return r.status


def main() -> int:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("⛔ SUPABASE_URL et SUPABASE_KEY requis (.env)."); return 1
    row = kpis_from_snapshot()
    try:
        code = push(row, url, key)
        print(f"✓ KPIs {row['date']} → Supabase (HTTP {code}) : "
              f"{', '.join(f'{k}={row[k]}' for k in row if k != 'date')}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"⛔ push Supabase : {e}\n   → vérifie SUPABASE_URL/KEY + table `daily_kpis` (cf. SQL).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
