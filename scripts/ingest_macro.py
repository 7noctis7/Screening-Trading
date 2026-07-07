#!/usr/bin/env python3
"""Vintages ALFRED RÉELS → data/macro.db (P1-3) — le point-in-time macro cesse d'être simulé.

  export FRED_API_KEY=...   (clé gratuite : fred.stlouisfed.org/docs/api/api_key.html)
  make ingest-macro         # sur le Mac (réseau requis)

ALFRED renvoie, pour chaque observation, sa `realtime_start` = date de PUBLICATION du
millésime. On la stocke comme `published` → `MacroStore.as_of(t)` ne sert QUE ce qui
était public à t (fini le look-ahead des révisions : le CPI de mars révisé en juin
n'existe pas pour un backtest daté d'avril).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.core.models import MacroObservation  # noqa: E402
from packages.storage import MacroStore  # noqa: E402

SERIES = ["UNRATE", "T10Y3M", "CPIAUCSL", "INDPRO"]   # chômage, courbe, inflation, prod indus
API = "https://api.stlouisfed.org/fred/series/observations"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s[:10]).replace(tzinfo=timezone.utc)


def _query(series: str, key: str, since: str, all_vintages: bool) -> list[MacroObservation]:
    params = {"series_id": series, "api_key": key, "file_type": "json",
              "observation_start": since}
    if all_vintages:                                   # ALFRED : toutes les révisions datées
        params.update({"realtime_start": since, "realtime_end": "9999-12-31"})
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
        data = json.load(r)
    out = []
    for o in data.get("observations", []):
        try:
            v = float(o["value"])
        except (KeyError, ValueError):
            continue                                   # "." = valeur manquante FRED
        # published = realtime_start si dispo (ALFRED), sinon la date d'obs (séries de
        # taux QUOTIDIENNES non révisées → publication ≈ date d'observation, PIT correct).
        pub = o.get("realtime_start") or o["date"]
        out.append(MacroObservation(series, _dt(o["date"]), v, _dt(pub)))
    return out


def fetch_vintages(series: str, key: str, since: str = "2000-01-01") -> list[MacroObservation]:
    """Publications d'une série depuis `since`. Essaie d'abord TOUTES les vintages (ALFRED) ;
    repli sur la série simple si l'API refuse (HTTP 400 : séries quotidiennes non révisées
    comme T10Y3M → le produit croisé date×vintage dépasse la limite FRED, or il n'y a de
    toute façon pas de révision → publication = date d'observation)."""
    try:
        return _query(series, key, since, all_vintages=True)
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        return _query(series, key, since, all_vintages=False)
    return out


def main() -> int:
    try:  # .env local
        from packages.common.env import load_env
        load_env()
    except Exception:  # noqa: BLE001
        pass
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("⛔ FRED_API_KEY absent (.env) — clé GRATUITE : "
              "https://fred.stlouisfed.org/docs/api/api_key.html")
        return 1
    db = os.environ.get("QUANT_MACRO_DB", "data/macro.db")
    store = MacroStore(db)
    total = 0
    for sid in SERIES:
        try:
            obs = fetch_vintages(sid, key)
            n = store.upsert(obs)
            total += n
            print(f"  {sid:10s} {len(obs):6d} vintages récupérés · {n} upserts")
        except Exception as e:  # noqa: BLE001
            print(f"  {sid:10s} échec ({str(e)[:60]}) — série ignorée, on continue")
    print(f"Terminé : {total} observations point-in-time → {db} ({store.count()} au total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
