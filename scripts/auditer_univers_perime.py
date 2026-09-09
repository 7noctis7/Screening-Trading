#!/usr/bin/env python3
"""Trie les symboles SANS NOM en « vraiment périmés » et « vivants » — sur les PRIX locaux.

POURQUOI NE PAS SE FIER AU SEUL 404 DU FOURNISSEUR. `make noms-univers` classe en « inconnu
du fournisseur » tout symbole que yfinance ne reconnaît pas. C'est un indice, pas une
preuve : un fournisseur peut ignorer un ticker parfaitement coté (changement de place, de
suffixe, panne de son côté). Conclure « délisté » sur cette seule base ferait sortir de
l'univers des titres vivants — et un titre retiré à tort ne se signale jamais, il manque
simplement, ce qui est indétectable.

Le juge objectif est dans VOS données : un titre délisté cesse d'avoir des barres. On lit
donc la date de la dernière barre locale, et on la compare à la barre la plus fraîche de
l'univers (seuil RELATIF : hors-ligne ou un week-end, un seuil absolu déclarerait tout
l'univers périmé). C'est la règle déjà appliquée par `build_snapshot`, pas une seconde.

    python scripts/auditer_univers_perime.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

SEUIL_JOURS = 10        # même valeur que le nettoyage de `build_snapshot`


def _sans_nom() -> list[tuple[str, str | None]]:
    out = []
    for chemin in sorted((RACINE / "data" / "seed").glob("*.csv")):
        with chemin.open(encoding="utf-8") as f:
            out += [(r["symbol"], (r.get("asset_class") or "").strip() or None)
                    for r in csv.DictReader(f)
                    if r.get("symbol") and not (r.get("name") or "").strip()]
    return sorted(set(out))


def _derniere_barre(symbole: str, classe: str | None) -> str | None:
    from packages.portfolio.user_analysis import _aliases, _bars_crypto
    from packages.data.price_loader import load_bars
    for alias in _aliases(symbole, classe):
        for barres in (load_bars(alias, years=2), _bars_crypto(alias, 2)):
            if barres:
                derniere = barres[-1]
                ts = derniere.get("t") if isinstance(derniere, dict) else getattr(derniere, "ts", None)
                return str(ts)[:10] if ts else None
    return None


def classer(dates: dict[str, str | None], seuil: int = SEUIL_JOURS) -> dict:
    """(limite, vivants, périmés, muets) — seuil RELATIF à la barre la plus fraîche.

    Un seuil ABSOLU (« moins de 10 jours par rapport à aujourd'hui ») déclarerait TOUT
    l'univers périmé un lundi férié, ou après une semaine sans ingestion. La référence est
    donc la barre la plus fraîche existante : elle bouge avec la base, pas avec l'horloge.
    C'est la règle déjà appliquée par `build_snapshot`, reprise et non réinventée.
    """
    from datetime import date, timedelta
    connues = [d for d in dates.values() if d]
    if not connues:
        return {"limite": None, "vivants": [], "perimes": [],
                "muets": sorted(dates), "mesurable": False}
    fraiche = max(connues)
    limite = (date.fromisoformat(fraiche) - timedelta(days=seuil)).isoformat()
    return {"limite": limite, "fraiche": fraiche, "mesurable": True,
            "vivants": sorted(s for s, d in dates.items() if d and d >= limite),
            "perimes": sorted(s for s, d in dates.items() if d and d < limite),
            "muets": sorted(s for s, d in dates.items() if not d)}


def principal() -> int:
    couples = _sans_nom()
    if not couples:
        print("Aucun symbole sans nom : rien à auditer.")
        return 0
    dates = {s: _derniere_barre(s, c) for s, c in couples}
    tri = classer(dates)
    if not tri["mesurable"]:
        print(f"{len(couples)} symbole(s) sans nom, AUCUN avec des barres locales.")
        print("Base de prix absente ou vide : impossible de trancher. Lancer `make ingest`.")
        return 1
    fraiche, limite = tri["fraiche"], tri["limite"]
    perimes, vivants, muets = tri["perimes"], tri["vivants"], tri["muets"]

    print(f"Barre la plus fraîche de l'univers : {fraiche} — seuil de péremption : {limite}\n")
    print(f"{len(vivants)} VIVANTS (barres récentes) — sans nom, mais À GARDER :")
    print("   ", ", ".join(f"{s} ({dates[s]})" for s in vivants[:30]) or "—")
    print(f"\n{len(perimes)} PÉRIMÉS (dernière barre < {limite}) — candidats au retrait :")
    print("   ", ", ".join(f"{s} ({dates[s]})" for s in perimes[:40]) or "—")
    print(f"\n{len(muets)} SANS AUCUNE BARRE locale — jamais ingérés, ou symbole invalide :")
    print("   ", ", ".join(muets[:40]) or "—")
    print("\nAucun fichier modifié : cet audit ne fait que MESURER.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
