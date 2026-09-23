#!/usr/bin/env python3
"""Coût réel du rebalancement quotidien — mesure avant décision.

  python scripts/turnover_audit.py

Lit `data/journal.db`. Si vide (conteneur cloud fraîchement cloné, ou avant le
premier `make journal-pull`), le dit clairement au lieu d'inventer un chiffre.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from packages.research.turnover_audit import rapport_complet
    from packages.storage import SqliteTradeJournal

    db = ROOT / "data" / "journal.db"
    if not db.exists():
        print("UNCALIBRATED — data/journal.db introuvable. "
              "Lance `make journal-pull` (si HF_TOKEN configuré) ou exécute ce "
              "script sur la machine qui détient le vrai journal (Mac mini / VPS).")
        return
    # LE PÉRIMÈTRE SE LIT SUR L'ORIGINE, PAS SUR `legacy` — troisième occurrence du
    # défaut nommé par l'ADR-0188, et la plus coûteuse : elle rendait la mesure
    # IMPOSSIBLE sans que rien ne le dise. Ce script lisait `all(legacy=False)`, or
    # `legacy` répond à « ce lot porte-t-il les features de la décision ? », pas à
    # « ce trade est-il au robot ? ». Depuis la reconstruction du journal depuis les
    # fills du courtier (18/09), presque tous les lots sont `legacy=1` : mesuré sur le
    # compte réel le 23/09, 609 lots au périmètre ROBOT dont QUATRE en `legacy=0`.
    # L'audit de rotation voyait donc UNE position fermée sur 578 — et rendait soit
    # UNCALIBRATED, soit un taux de rotation calculé sur une seule ligne, ce qui aurait
    # eu toutes les apparences d'une mesure.
    #
    # Rien de ce que calcule `auditer` n'a besoin des features : il lit `exit_ts`,
    # `pnl_pct`, `mfe`, `duration_s`, `exit_reason`, `fees`. Les lots rejoués les
    # portent. Le filtre n'écartait pas des données inutilisables, il écartait 99 % de
    # la mesure.
    from packages.execution.perimetre_journal import pris_par_le_robot
    tous = SqliteTradeJournal(str(db)).all()
    trades = [t for t in tous if pris_par_le_robot(t.id)]
    hors = len(tous) - len(trades)
    print(f"Périmètre : {len(trades)} lot(s) du ROBOT sur {len(tous)} au journal"
          + (f" · {hors} hors périmètre (import de provenance inconnue)."
             if hors else "."))
    print(rapport_complet(trades))


if __name__ == "__main__":
    main()
