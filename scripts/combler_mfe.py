#!/usr/bin/env python3
"""Calcule MFE/MAE sur les trades clos qui n'en ont pas. SIMULATION PAR DÉFAUT.

    python scripts/combler_mfe.py               # simule, n'écrit RIEN
    python scripts/combler_mfe.py --appliquer   # écrit, après sauvegarde

N'écrit QUE `mfe` et `mae`. Ne touche jamais un prix, une quantité, une date ni un P&L :
ce script mesure le chemin du marché entre l'entrée et la sortie, il ne reconstruit
aucune décision. Une mesure déjà présente n'est jamais réécrite.

Sans hauts/bas exploitables, la ligne est laissée telle quelle — une MFE calculée sur
des clôtures seules sous-estime l'excursion et flatterait la qualité des sorties.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import logging as _lg  # noqa: E402

for _n in ("yfinance", "urllib3", "peewee"):  # yfinance dumpe des pages HTML
    _lg.getLogger(_n).setLevel(_lg.CRITICAL)

from packages.data.price_loader import load_bars  # noqa: E402
from packages.research.excursions import combler, rapport  # noqa: E402
from packages.storage.journal_sqlite import DEFAULT_DB, SqliteTradeJournal  # noqa: E402


def _sauvegarde(chemin: Path) -> Path:
    horo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cible = chemin.with_suffix(f".avant-mfe-{horo}.db")
    shutil.copy2(chemin, cible)
    return cible


def _apercu(trades: list, avant: dict, n: int = 8) -> None:
    """Montre ce qui serait écrit — une simulation muette ne se vérifie pas."""
    modifs = [t for t in trades if t.mfe is not None and avant.get(t.id) is None]
    if not modifs:
        return
    print(f"\nAperçu ({min(n, len(modifs))} sur {len(modifs)}) :")
    print(f"  {'actif':<12} {'entrée':>10} {'MFE':>8} {'MAE':>8}  capture")
    for t in modifs[:n]:
        mesurable = t.pnl_pct is not None and t.mfe and t.mfe > 1e-9
        cap = f"{t.pnl_pct / t.mfe:6.0%}" if mesurable else "   n/d"
        print(f"  {t.instrument:<12} {t.entry_price:10.4f} {t.mfe:8.2%} "
              f"{t.mae or 0:8.2%}  {cap}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--appliquer", action="store_true",
                    help="écrit réellement (défaut : simulation)")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="chemin du journal")
    ap.add_argument("--annees", type=int, default=3, help="profondeur d'historique")
    a = ap.parse_args()

    chemin = Path(a.db)
    if not chemin.exists():
        print(f"✗ journal introuvable : {chemin}")
        return 1

    journal = SqliteTradeJournal(chemin)
    tous = journal.all(legacy=False) + journal.all(legacy=True)
    avant = {t.id: t.mfe for t in tous}
    res = combler(tous, lambda s: load_bars(s, years=a.annees))
    print(rapport(res))
    _apercu(res["trades"], avant)

    if not res["combles"]:
        print("\nRien à appliquer.")
        return 0
    if not a.appliquer:
        print(f"\nSIMULATION — aucune écriture. {res['combles']} ligne(s) seraient "
              "complétées (mfe/mae uniquement). Relancer avec --appliquer.")
        return 0

    copie = _sauvegarde(chemin)
    print(f"\nSauvegarde : {copie}")
    n = 0
    for t in res["trades"]:
        if t.mfe is not None and avant.get(t.id) is None:
            journal.conn.execute("UPDATE trades SET mfe=?, mae=? WHERE id=?",
                                 (t.mfe, t.mae, t.id))
            n += 1
    journal.conn.commit()
    print(f"✓ {n} ligne(s) complétée(s). Restauration : cp {copie} {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
