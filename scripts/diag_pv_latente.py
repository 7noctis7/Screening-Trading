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

CE QU'IL LIT, ET CE QU'IL NE LIT PAS. La source est `journal.db` — les lots que le
SYSTÈME croit ouverts. Ce n'est PAS ce que le courtier détient. Mesuré le 10/09 : le
journal portait trois lots QQQ « ouverts » pour 69 456 $ quand le courtier n'en détenait
qu'un, à 43 562 $ — 25 894 $ de fantômes, fermés chez le courtier et jamais fermés au
journal. Les valeurs ci-dessous décrivent donc la TRAJECTOIRE des lots journalisés, pas
l'exposition réelle. Pour celle-ci : `make live` (dry-run sur le compte réel).

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
    # La base LOCALE d'abord. Le premier passage réel interrogeait Yahoo avec le
    # symbole nu (« AAVE », « SOL ») et récoltait des 404 bruyants, alors que
    # `crypto.db` contient la série sous `AAVE-USD` depuis les réparations du 09/09.
    # Un diagnostic qui lit un journal local n'a aucune raison d'appeler le réseau
    # tant qu'il n'a pas épuisé ce qu'il a sous la main.
    for alias in _aliases(symbole, classe):
        lot = _bars_crypto(alias, 5)
        if lot:
            return [(str(b.ts)[:10], float(b.close)) for b in lot]
    for alias in _aliases(symbole, classe):
        lot = load_bars(alias, years=5)
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


def _valeur(f: dict) -> float:
    return f["prix_entree"] * f["qty"] + f["pv_courante"]


def _concentration(fiches: list[dict]) -> None:
    """Le poids de chaque instrument dans le portefeuille, plus lourd d'abord.

    C'est la première chose à regarder devant un total qui oscille : un portefeuille
    concentré bouge comme sa plus grosse ligne, et aucune règle de sortie n'y change
    quoi que ce soit. Les LOTS sont regroupés par instrument — trois achats du même ETF
    font une seule exposition, même s'ils font trois lignes au journal.
    """
    par_titre: dict[str, float] = {}
    for f in fiches:
        par_titre[f["symbole"]] = par_titre.get(f["symbole"], 0.0) + _valeur(f)
    total = sum(par_titre.values())
    if total <= 0:
        return
    lourds = sorted(par_titre.items(), key=lambda kv: -kv[1])
    print(f"\n  CONCENTRATION — {len(par_titre)} instrument(s), "
          f"{total:,.0f} $ investis")
    for nom, val in lourds[:8]:
        print(f"    {nom[:16]:16s} {val:>10,.0f} $   {100 * val / total:>5.1f} %")
    tete = 100 * lourds[0][1] / total
    if tete >= 25:
        print(f"    ⚠ la première ligne pèse {tete:.0f} % du portefeuille.")
        print("      Un total qui oscille suit d'abord CELA, pas une règle")
        print("      de sortie manquante.")


def _incoherences(fiches: list[dict]) -> None:
    """Lots dont la PV latente est impossible au vu de leur taille.

    Une position longue ne peut pas perdre plus qu'elle ne vaut. Quand c'est le cas,
    ce n'est pas le marché : c'est `avg_price` ou `qty` qui est faux au journal. On le
    signale à part plutôt que de le laisser polluer les totaux — un chiffre faux
    mélangé à des chiffres justes les salit tous.
    """
    suspects = [f for f in fiches
                if f.get("available") and f["pv_courante"] < 0
                and abs(f["pv_courante"]) > max(1.0, _valeur(f))]
    if not suspects:
        return
    print(f"\n  ⚠ {len(suspects)} lot(s) INCOHÉRENT(s) — perte supérieure à la valeur")
    print("    de la position : `avg_price` ou `qty` est faux au journal, pas le")
    print("    marché. Ces lignes faussent tout total qui les inclut.")
    for f in suspects[:10]:
        print(f"      · {f['symbole'][:14]:14s} PV {f['pv_courante']:>10,.0f} $ "
              f"pour une position de {_valeur(f):>9,.0f} $")
    print("    → `make diag-journal`, puis la réconciliation (P0 du TODO).")


def _imprimer(fiches: list[dict], capital: float) -> None:
    from packages.portfolio.pv_latente import agreger
    utiles = sorted([f for f in fiches if f.get("available")],
                    key=lambda f: -f["rendu_du_gain"])
    print(f"\n  {'position':16s} {'valeur':>10s} {'PV pic':>9s} {'PV jour':>9s} "
          f"{'gain rendu':>11s} {'part':>6s}")
    for f in utiles[:25]:
        print(f"  {f['symbole'][:16]:16s} {_valeur(f):>10,.0f} {f['pv_max']:>9,.0f} "
              f"{f['pv_courante']:>9,.0f} {f['rendu_du_gain']:>11,.0f} "
              f"{100 * f['part_rendue']:>5.0f}%")
    t = agreger(fiches)
    print(f"\n  {t['n_positions']} position(s) mesurée(s), dont "
          f"{t['n_jamais_en_gain']} jamais passée(s) en gain")
    print(f"  somme des gains maximaux : {t['somme_des_gains_max']:>10,.0f} $ "
          "(pics non simultanés)")
    print(f"  GAIN RENDU               : {t['rendu_du_gain']:>10,.0f} $ "
          f"({100 * t['part_rendue']:.0f} % de ces pics) ← le yo-yo")
    print(f"  perte sous l'entrée      : {t['perte_sous_entree']:>10,.0f} $ "
          "← autre problème : un stop, pas un objectif")
    print(f"  PV latente du jour       : {t['pv_courante']:>10,.0f} $")
    _incoherences(fiches)
    _concentration(utiles)
    bande = max(BANDE_PART_CAPITAL * capital, 5.0)
    print(f"\n  Pour mémoire, la bande d'inaction vaut {bande:,.0f} $ — mais elle "
          "compare")
    print("  l'écart |cible − détenu| en VALEUR, pas la plus-value. Les cibles du")
    print("  jour ne sont pas ici : `make live-sim` montre les décisions réelles.")


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
    print("   ⚠ source = JOURNAL, pas courtier. Un lot fermé chez le courtier et non")
    print("     fermé ici reste compté : `make live` donne l'exposition réelle.")
    _imprimer(analyser(positions), a.capital)


if __name__ == "__main__":
    main()
