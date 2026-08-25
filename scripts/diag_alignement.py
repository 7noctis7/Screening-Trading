"""make diag-alignement — d'OÙ vient le gain de l'alignement par date ?

Le labo du 25/08 promeut « +alignement par date » : ΔSharpe +0,42, ΔmaxDD +8,4 pts, DSR 99 %.
C'est le premier candidat jamais promu par ce gate. Avant d'activer quoi que ce soit en
production, il faut savoir LAQUELLE de ces deux causes produit le gain — elles n'ont pas du tout
la même valeur :

  A. CORRECTION D'UN DÉFAUT RÉEL. L'empilement positionnel superposait les `L` dernières barres
     de chaque série en supposant un calendrier commun. Avec 929 instruments mêlant actions,
     ETF, crypto (7 j/7), forex et commodités, ces calendriers DIFFÈRENT. Un prix crypto d'un
     dimanche pouvait être aligné sur une séance actions du vendredi. Si c'est la cause, le gain
     est structurel et l'activation s'impose.

  B. UN TIRAGE D'UNIVERS DIFFÉRENT. `fenetre_commune` retenait 747 noms sur 929 ; l'alignement
     par date les retient tous. L'univers top-30 sélectionné n'est donc pas le même, et un
     univers différent donne un résultat différent — sans qu'aucun défaut n'ait été corrigé.
     Si c'est la cause, le « gain » est une chance de tirage et l'activer serait du p-hacking.

Le test isole les deux : on relance l'alignement par date en le RESTREIGNANT aux seuls noms que
le mode positionnel avait retenus. À univers comparable, ce qui reste est l'effet d'alignement.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _ligne(titre: str, r: dict) -> str:
    st = r.get("preset") or {}
    p = r.get("panel") or {}
    return (f"  {titre:34s} Sharpe {st.get('sharpe', 0):5.2f} · CAGR {st.get('annualized', 0)*100:5.1f}% "
            f"· maxDD {st.get('max_drawdown', 0)*100:6.1f}% · {r.get('n_steps', 0):3d} pas "
            f"· {p.get('n_retenus', 0)} noms")


def main() -> int:
    from packages.backtest.preset_backtest import preset_backtest
    from scripts.preset_lab import _load_real_data

    data, acmap = _load_real_data()
    if data is None:
        return 1

    print("\n" + "=" * 78)
    print("D'OÙ VIENT LE GAIN DE L'ALIGNEMENT PAR DATE ?")
    print("=" * 78)

    pos = preset_backtest(data, asset_classes=acmap, aligner_dates=False)
    dat = preset_backtest(data, asset_classes=acmap, aligner_dates=True)
    if not (pos.get("available") and dat.get("available")):
        print("⛔ un des deux backtests est indisponible."); return 1

    print("\n1. LES DEUX MODES, UNIVERS LIBRE")
    print(_ligne("positionnel (production)", pos))
    print(_ligne("aligné par date", dat))

    u_pos, u_dat = set(pos.get("univers") or []), set(dat.get("univers") or [])
    commun = u_pos & u_dat
    print(f"\n2. LES UNIVERS SÉLECTIONNÉS SONT-ILS LES MÊMES ?")
    print(f"  positionnel     : {len(u_pos)} titres")
    print(f"  aligné par date : {len(u_dat)} titres")
    print(f"  en commun       : {len(commun)} "
          f"({len(commun)/max(1, len(u_pos)):.0%} de l'univers positionnel)")
    if u_pos - u_dat:
        print(f"  seulement positionnel : {', '.join(sorted(u_pos - u_dat)[:12])}")
    if u_dat - u_pos:
        print(f"  seulement par date    : {', '.join(sorted(u_dat - u_pos)[:12])}")

    if u_pos == u_dat:
        print("\n→ univers IDENTIQUES : tout l'écart vient de l'alignement. Cause A, gain structurel.")
        return 0

    # 3. À UNIVERS COMPARABLE : on restreint l'alignement par date aux noms du mode positionnel.
    noms_pos = [s for s, b in data.items() if b and len(b) > 0]
    retenus = pos.get("panel", {}).get("n_retenus", 0)
    sous = {s: data[s] for s in noms_pos if s in _noms_panel(data, pos)} or data
    print(f"\n3. À UNIVERS COMPARABLE ({len(sous)} noms, ceux que le positionnel retenait)")
    ctrl = preset_backtest(sous, asset_classes=acmap, aligner_dates=True)
    if not ctrl.get("available"):
        print("  ⛔ indisponible sur ce sous-ensemble."); return 1
    print(_ligne("positionnel (référence)", pos))
    print(_ligne("aligné par date, mêmes noms", ctrl))

    d_total = dat["preset"]["sharpe"] - pos["preset"]["sharpe"]
    d_align = ctrl["preset"]["sharpe"] - pos["preset"]["sharpe"]
    print(f"\n4. DÉCOMPOSITION DU ΔSharpe DE {d_total:+.2f}")
    print(f"  effet ALIGNEMENT (à univers comparable) : {d_align:+.2f}")
    print(f"  effet UNIVERS    (le reste)             : {d_total - d_align:+.2f}")
    print()
    if abs(d_align) >= 0.7 * abs(d_total) and d_align > 0:
        print("  → l'essentiel vient de l'ALIGNEMENT : cause A, correction d'un défaut réel.")
        print("    Activer en production se justifie, avec ces chiffres dans la PR.")
    elif abs(d_align) <= 0.3 * abs(d_total):
        print("  → l'essentiel vient du TIRAGE D'UNIVERS : cause B. Le « gain » n'est pas une")
        print("    correction, c'est une chance de tirage. NE PAS activer sur cette base :")
        print("    l'alignement reste correct en soi, mais il faut le justifier autrement.")
    else:
        print("  → causes MÊLÉES. Ni l'une ni l'autre ne domine : re-tester sur une période")
        print("    disjointe avant toute activation.")
    return 0


def _noms_panel(data: dict, res: dict) -> set:
    """Noms que la fenêtre commune retenait — recalculés à l'identique (le backtest ne les
    publie pas, seul leur nombre l'est)."""
    from packages.backtest.panel import fenetre_commune

    eligibles = [s for s, b in data.items() if b and len(b) > 120 + 2 * 21]
    syms, _L, _d = fenetre_commune(data, eligibles)
    return set(syms)


if __name__ == "__main__":
    sys.exit(main())
