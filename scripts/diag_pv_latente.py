"""Combien de plus-value latente le portefeuille a-t-il rendue ? — et pourquoi.

  python scripts/diag_pv_latente.py            # lecture seule, n'écrit rien

CE QUI A DÉCLENCHÉ CE SCRIPT (10/09) : « ma PV latente chute et je ne parviens pas à la
sécuriser, mon total fait le yo-yo ». Le tableau de bord montre la PV du jour, jamais le
chemin — une ligne montée à +900 € puis redescendue à +120 € y ressemble trait pour
trait à une ligne montée tout droit à +120 €.

Deux tableaux, et ils répondent à deux questions différentes.

  1. CE QUI A ÉTÉ RENDU, ligne par ligne : pic de PV latente depuis l'entrée, PV du
     jour, écart. C'est le yo-yo, chiffré.
  2. CE QUE LE REBALANCEMENT PEUT SÉCURISER. Le moteur de production n'a ni objectif de
     gain ni stop : sa SEULE sortie est le rebalancement vers les poids cibles, et il
     ne bouge une ligne que si l'écart à sa cible dépasse la bande d'inaction —
     0,5 % du capital. Une ligne dont l'écart reste sous cette bande ne peut pas être
     allégée, quoi qu'elle gagne. Le tableau dit lesquelles sont dans ce cas.

RIEN N'EST DÉCIDÉ ICI. Ajouter une règle de prise de bénéfice change le moteur qui
tourne en production : c'est un choix à valider pour lui-même (ADR-0073), pas un
réglage. Ce script fournit les chiffres qui permettent de le trancher.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BANDE_PART_CAPITAL = 0.005     # bande d'inaction de run_live.py : 0,5 % du capital


def positions_ouvertes(chemin: Path) -> list[dict]:
    """Lots encore ouverts du journal réel. Liste vide si la base manque."""
    import sqlite3
    if not chemin.exists():
        return []
    conn = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        lignes = conn.execute(
            "SELECT id, instrument, asset_class, side, qty, entry_ts, avg_price "
            "FROM trades WHERE exit_ts IS NULL AND qty > 0").fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [dict(r) for r in lignes]


def _barres(symbole: str, classe: str) -> list[tuple[str, float]]:
    """[(date, clôture)] via les MÊMES alias que le reste du projet."""
    try:
        from packages.portfolio.user_analysis import _aliases, _bars_crypto, load_bars
    except Exception:  # noqa: BLE001
        return []
    for alias in _aliases(symbole, classe):
        for lot in (load_bars(alias, years=5), _bars_crypto(alias, 5)):
            if lot:
                return [(str(b.ts)[:10], float(b.close)) for b in lot]
    return []


def analyser(positions: list[dict]) -> list[dict]:
    from packages.portfolio.pv_latente import pv_rendue
    out = []
    for p in positions:
        barres = _barres(p["instrument"], p.get("asset_class") or "equity")
        fiche = pv_rendue(barres, str(p["entry_ts"])[:10], float(p["avg_price"]),
                          float(p["qty"]), (p.get("side") or "long").lower())
        fiche.update(symbole=p["instrument"], qty=float(p["qty"]),
                     prix_entree=float(p["avg_price"]))
        out.append(fiche)
    return out


def _imprimer(fiches: list[dict], capital: float) -> None:
    from packages.portfolio.pv_latente import agreger
    bande = max(BANDE_PART_CAPITAL * capital, 5.0)
    utiles = sorted([f for f in fiches if f.get("available")],
                    key=lambda f: -f["rendu"])
    print(f"\n  {'position':16s} {'PV pic':>10s} {'PV jour':>10s} {'rendu':>10s} "
          f"{'part':>7s}  sécurisable ?")
    for f in utiles[:25]:
        valeur = f["prix_entree"] * f["qty"] + f["pv_courante"]
        secu = "oui" if f["pv_courante"] >= bande else f"non (< {bande:,.0f} $)"
        print(f"  {f['symbole'][:16]:16s} {f['pv_max']:>10,.0f} "
              f"{f['pv_courante']:>10,.0f} {f['rendu']:>10,.0f} "
              f"{100 * f['part_rendue']:>6.0f}%  {secu:s}   ({valeur:,.0f} $)")
    total = agreger(fiches)
    print(f"\n  {total['n_positions']} position(s) ouverte(s) mesurée(s)")
    print(f"  somme des pics : {total['somme_des_pics']:,.0f} $  — jamais atteinte "
          "d'un seul coup, les pics ne sont pas simultanés")
    print(f"  PV du jour     : {total['pv_courante']:,.0f} $")
    print(f"  RENDU          : {total['rendu']:,.0f} $ "
          f"({100 * total['part_rendue']:.0f} % de la somme des pics)")
    bloquees = [f for f in utiles if 0 < f["pv_courante"] < bande]
    print(f"\n  BANDE D'INACTION : {bande:,.0f} $ (0,5 % du capital)")
    print(f"  {len(bloquees)} ligne(s) en gain sous cette bande : le rebalancement ne")
    print("  peut PAS les alléger, quoi qu'elles")
    print("  gagnent. Leur plus-value ne peut que revenir. C'est le premier suspect du")
    print("  yo-yo, avant toute règle de prise de bénéfice.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--journal", default=str(ROOT / "data" / "journal.db"))
    ap.add_argument("--capital", type=float, default=100_000.0,
                    help="capital du courtier (fixe la bande d'inaction)")
    a = ap.parse_args()

    positions = positions_ouvertes(Path(a.journal))
    if not positions:
        print(f"\n⛔ Aucune position ouverte dans {a.journal}.")
        print("   UNCALIBRATED : sans journal réel, ce script n'a rien à mesurer et")
        print("   n'inventera rien. Lancer depuis la machine qui le détient.")
        return
    print(f"\n{len(positions)} position(s) ouverte(s) — journal : {a.journal}")
    _imprimer(analyser(positions), a.capital)


if __name__ == "__main__":
    main()
