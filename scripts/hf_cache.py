#!/usr/bin/env python3
"""Cache OHLCV ↔ dataset Hugging Face (gratuit, versionné, souverain).

  python scripts/hf_cache.py push            # bases locales → parquet → upload HF (HF_TOKEN requis)
  python scripts/hf_cache.py pull            # parquet HF (public, sans token) → data/<db>.db (SQLite)
  python scripts/hf_cache.py push --dbs market crypto --dataset Noctis777/screening-trading-cache

`pull` est utilisé en CI pour repartir d'un socle propre (fini le rate-limit yfinance) ; yfinance
ne fait ensuite qu'un top-up incrémental. `push` (local ou cron avec HF_TOKEN) rafraîchit le cache.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data import hf_cache  # noqa: E402
from packages.data.engine import read_prices_rows  # noqa: E402


def _push(dbs: list[str], dataset_id: str, token: str | None) -> int:
    import os
    import pandas as pd
    from huggingface_hub import HfApi

    token = token or os.environ.get("HF_TOKEN")
    if not token:
        print("⛔ HF_TOKEN absent (.env ou env). Pousse impossible."); return 1
    api = HfApi(token=token)
    api.create_repo(repo_id=dataset_id, repo_type="dataset", exist_ok=True)
    cache = ROOT / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    pushed = 0
    for db in dbs:
        rows = read_prices_rows(db)
        if not rows:
            print(f"· {db} : base absente/vide — ignorée"); continue
        df = pd.DataFrame(rows).rename(columns={"ts": "date"})
        keep = [c for c in ("symbol", "date", "open", "high", "low", "close", "volume") if c in df.columns]
        local = cache / f"{db}.parquet"
        df[keep].to_parquet(local, index=False)
        api.upload_file(path_or_fileobj=str(local), path_in_repo=f"{db}.parquet",
                        repo_id=dataset_id, repo_type="dataset")
        print(f"✓ {db}.parquet poussé ({len(df)} lignes) → {dataset_id}")
        pushed += 1
    return 0 if pushed else 1


def _pull(dbs: list[str], dataset_id: str) -> int:
    total = 0
    for db in dbs:
        rows = hf_cache.read_parquet_rows(db, dataset_id)
        if not rows:
            print(f"· {db} : pas de cache HF (ou vide) — yfinance prendra le relais"); continue
        n = hf_cache.write_sqlite(rows, ROOT / "data" / f"{db}.db")
        print(f"✓ {db}.db reconstruit depuis le cache HF ({n} lignes)")
        total += n
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Cache OHLCV ↔ Hugging Face Dataset.")
    ap.add_argument("action", choices=["push", "pull"])
    ap.add_argument("--dbs", nargs="*", default=["market", "crypto"])
    ap.add_argument("--dataset", default=hf_cache.dataset())
    ap.add_argument("--token", default=None)
    a = ap.parse_args()
    return _push(a.dbs, a.dataset, a.token) if a.action == "push" else _pull(a.dbs, a.dataset)


if __name__ == "__main__":
    raise SystemExit(main())
