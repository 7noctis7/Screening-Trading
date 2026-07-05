#!/usr/bin/env python3
"""Journal de trades ↔ dataset Hugging Face PRIVÉ (persistance du runner cloud, 0 €).

Le runner paper GitHub Actions (`.github/workflows/paper.yml`) est éphémère : sans
persistance, `data/journal.db` (features de décision + round-trips, P0-4) serait
perdu à chaque run. Ce script le synchronise avec un dataset HF **PRIVÉ** :

  python scripts/hf_journal.py pull    # HF → data/journal.db (avant le run)
  python scripts/hf_journal.py push    # data/journal.db → HF (après le run)

⚠️ CONFIDENTIALITÉ : le journal contient tes trades paper (positions réelles courtier
= local-only, garde-fou CLAUDE.md). Le dataset DOIT être PRIVÉ — `push` le crée en
privé et REFUSE de pousser s'il s'avère public. `HF_TOKEN` requis (pull ET push :
dataset privé). Sans token/dataset → sortie code 0 avec message (best-effort, ne
casse jamais le run de réconciliation).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "journal.db"
DEFAULT_DATASET = "Noctis777/quant-journal"
FILENAME = "journal.db"


def _dataset() -> str:
    return os.environ.get("QUANT_HF_JOURNAL", DEFAULT_DATASET)


def _token() -> str | None:
    try:  # .env local (jamais commité) — no-op si absent
        from packages.common.env import load_env
        load_env()
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get("HF_TOKEN")


def pull() -> int:
    token = _token()
    if not token:
        print("· HF_TOKEN absent → pas de pull journal (dataset privé). "
              "Journal local inchangé.")
        return 0
    try:
        from huggingface_hub import hf_hub_download
        p = hf_hub_download(repo_id=_dataset(), repo_type="dataset",
                            filename=FILENAME, token=token)
        DB.parent.mkdir(parents=True, exist_ok=True)
        DB.write_bytes(Path(p).read_bytes())
        print(f"✓ journal récupéré ({DB.stat().st_size:,} octets) ← {_dataset()}")
        return 0
    except Exception as e:  # noqa: BLE001 — 1er run : dataset/fichier inexistant = normal
        print(f"· pas de journal distant ({type(e).__name__}) — départ local propre.")
        return 0


def push() -> int:
    token = _token()
    if not token:
        print("· HF_TOKEN absent → journal NON persisté "
              "(le prochain run cloud repartira sans lui).")
        return 0
    if not DB.exists():
        print("· data/journal.db absent — rien à pousser.")
        return 0
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
        api.create_repo(repo_id=_dataset(), repo_type="dataset",
                        private=True, exist_ok=True)
        info = api.repo_info(repo_id=_dataset(), repo_type="dataset")
        if not getattr(info, "private", False):     # garde-fou repo PUBLIC → refus
            print(f"⛔ {_dataset()} est PUBLIC — push refusé (journal confidentiel). "
                  f"Passe le dataset en privé sur huggingface.co puis relance.")
            return 1
        api.upload_file(path_or_fileobj=str(DB), path_in_repo=FILENAME,
                        repo_id=_dataset(), repo_type="dataset",
                        commit_message="journal paper (runner cloud)")
        print(f"✓ journal poussé ({DB.stat().st_size:,} octets) → {_dataset()} (privé)")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"⚠ push journal échoué ({str(e)[:80]}) — le run n'est PAS invalidé.")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync data/journal.db ↔ dataset HF privé")
    ap.add_argument("action", choices=["pull", "push"])
    a = ap.parse_args()
    return pull() if a.action == "pull" else push()


if __name__ == "__main__":
    sys.exit(main())
