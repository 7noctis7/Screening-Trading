#!/usr/bin/env python3
"""Notionnel contre risque constant, sur les données RÉELLES et à signaux identiques.

POURQUOI CE BANC EXISTE. La comparaison en R (t = 0,94 en dollars contre 2,00 en R sur
les 477 trades) est une CONTREFACTUELLE : elle dit ce qu'on aurait obtenu à risque égal
en supposant les mêmes entrées et les mêmes sorties. Or redimensionner change le capital
disponible, donc les trades qu'on peut prendre. L'indication est forte ; elle n'est pas
la preuve. Seul un re-run complet tranche, et c'est ce que fait ce script.

Il rejoue le backtest de production, à paramètres identiques, en ne changeant QUE le
dimensionnement, puis compare les deux courbes par le test de Jobson-Korkie corrigé
Memmel — apparié, car les deux séries partagent le même marché et le même calendrier.

    python scripts/sizing_lab.py                 # 0 (actuel) vs 0.5 %, 1 %, 2 %
    python scripts/sizing_lab.py 0.01 0.015      # fractions de risque au choix
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RISQUES = [0.005, 0.01, 0.02]
RISQUE_PROD = 0.005              # réglage de production (ADR-0051)
# Cibles exprimées en FRACTION de la volatilité réalisée de la référence, et non en
# valeur absolue. Une grille absolue (10/15/20 %) s'est révélée entièrement INERTE :
# ce portefeuille tourne à ~52 % d'exposition, sa vol est donc bien en dessous de celle
# d'un indice, le plafond ne mordait jamais et les trois variantes rendaient des courbes
# identiques au centime. Un levier qui ne fait rien est pire qu'un levier absent : il se
# lit comme « mesuré, sans effet ».
FRACTIONS_VOL = [0.5, 0.7, 0.9]


def _donnees():
    """Le MÊME univers et la même fenêtre que la production — sinon on compare deux
    expériences différentes et l'écart mesuré ne veut plus rien dire."""
    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    instruments = _seed_universe()
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    secteur = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    debut = fin - timedelta(days=_HISTORY_DAYS)
    data, mode, reels = _load_prices(instruments, secteur, debut, fin, 7)
    if len(reels) >= 30:            # zéro prix synthétique dans un banc de décision
        data = {s: b for s, b in data.items() if s in reels}
    return data, acmap, mode, len(reels), debut, fin


def empreinte(data: dict, provenance_vix: str) -> str:
    """Signature du jeu de données. Deux runs ne se comparent QUE si elle est identique.

    Constaté le 02/09 : la même configuration a donné Sharpe 0,65 puis 0,38 à un jour
    d'écart, sur un appel au backtest identique au caractère près. Sans empreinte
    affichée, on aurait cru à un effet du réglage.
    """
    barres = sum(len(b) for b in data.values())
    fin_reelle = max((b[-1].ts for b in data.values() if b), default=None)
    jour = fin_reelle.date().isoformat() if fin_reelle else "?"
    return (f"{len(data)} titres · {barres:,} barres · dernière {jour} · "
            f"{provenance_vix}")


def _vix(data, debut, fin, seed: int = 7):
    """Le VIX de PRODUCTION, et non son absence. Renvoie (série, provenance).

    LA PROVENANCE EST RENVOYÉE, PAS DEVINÉE. `_index_closes` lit la base puis, si la
    série est périmée, INTERROGE LE RÉSEAU. Un banc de décision dont le résultat dépend
    silencieusement de la réussite d'un appel réseau n'est pas reproductible : deux runs
    à un jour d'écart peuvent alors comparer un VIX réel à un VIX synthétique sans que
    rien ne l'indique — et le multiplicateur d'exposition (×1,0 / ×0,7 / ×0,4) suffit à
    déplacer tous les chiffres. On publie donc d'où vient la série.

    `fast_swing` module l'exposition brute autorisée par `vix_exposure` : ×1,0 sous 20,
    ×0,7 entre 20 et 30, ×0,4 au-delà. Sans série VIX le multiplicateur reste à 1,0 —
    donc au MAXIMUM en permanence, y compris dans les krachs. Or c'est `allowed_gross`
    qui détermine `room`, et `room` est exactement le mécanisme qu'on teste : un banc
    sans VIX sous-représente les troncatures qu'il est censé mesurer.
    """
    from apps.api.snapshot import _index_closes, _vix_series
    n = max(len(b) for b in data.values())
    reel, est_reel = _index_closes(["^VIX", "VIX"], debut, fin, [])
    if est_reel and len(reel) >= 50:
        serie = reel[-n:] if len(reel) >= n else [reel[0]] * (n - len(reel)) + reel
        return serie, "VIX RÉEL"
    return _vix_series(n, seed), "VIX SYNTHÉTIQUE (repli — résultats non comparables)"


def _expo_moyenne(trades, equity: list[float], jours: int) -> float:
    """Exposition brute moyenne, pondérée par le TEMPS de détention.

    Sans elle, on compare deux dimensionnements ET deux niveaux de levier à la fois :
    un net trois fois plus bas peut ne signifier qu'un portefeuille trois fois moins
    investi, ce qui ne dit rien de la qualité de la règle de taille.
    """
    if not equity or jours <= 0:
        return 0.0
    moy_eq = sum(equity) / len(equity)
    jour = 86400.0
    engage = sum(t.qty * t.entry_price
                 * max((t.exit_ts - t.entry_ts).total_seconds(), 0.0) / jour
                 for t in trades if t.exit_ts and t.entry_ts)
    return engage / (jours * moy_eq) if moy_eq > 0 else 0.0


def _run(data, acmap, risque: float, vix=None, vol_cible: float = 0.0):
    from packages.backtest.fast_swing import fast_swing_backtest
    from packages.execution.costs import CostModel
    from packages.portfolio import fragilite as F

    _, journal, equity, horodatage = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=6.0, vix=vix, close_at_end=False, daily_max_loss=0.06,
        trail_atr=5.0, next_open_fills=True, risque_par_trade=risque,
        vol_cible=vol_cible)
    trades = [t for t in journal.all() if t.pnl_net is not None]
    trades.sort(key=lambda t: t.exit_ts or t.entry_ts)
    pnls = [t.pnl_net for t in trades]
    rs = [t.r_multiple for t in trades]
    return {"equity": equity, "horodatage": horodatage,
            "n": len(pnls), "net": sum(pnls),
            "expo": _expo_moyenne(trades, equity, len(equity)),
            **F.marge_de_payoff(pnls), **F.concentration(pnls),
            **F.significativite(pnls), **F.dependance(pnls),
            **F.comparer_dimensionnement(pnls, rs)}


def _vol_annualisee(rends: list[float]) -> float:
    """Volatilité annualisée d'une série de rendements quotidiens."""
    import statistics as st
    return st.pstdev(rends) * (252 ** 0.5) if len(rends) > 1 else 0.0


def _psr_dsr(rends: list[float], n_essais: int) -> tuple[float, float]:
    """PSR et DSR — mêmes fonctions et même périodicité QUOTIDIENNE que le dashboard.

    Le PSR est P(Sharpe vrai > 0). Le DSR relève ce seuil du nombre d'ESSAIS : le
    maximum de N Sharpe bruités croît en sqrt(2 ln N), si bien qu'un beau chiffre obtenu
    après vingt tentatives ne vaut pas un beau chiffre obtenu du premier coup. Le compte
    d'essais inclut ici les variantes de ce banc — les compter est conservateur, et
    c'est le bon sens de l'erreur.
    """
    import statistics as st

    from packages.portfolio.psr import deflated_sharpe_ratio, probabilistic_sharpe_ratio
    n = len(rends)
    if n < 30:
        return 0.0, 0.0
    ec = st.pstdev(rends)
    if ec <= 0:
        return 0.0, 0.0
    sr = st.fmean(rends) / ec                              # Sharpe QUOTIDIEN
    return (probabilistic_sharpe_ratio(sr, n, sr_benchmark=0.0),
            deflated_sharpe_ratio(sr, n, n_trials=n_essais))


def _essais(n_variantes: int) -> int:
    """Essais déjà consommés par le projet (registre de recherche) + ceux de ce banc."""
    try:
        from packages.research.ledger import deflation_params
        deja, _ = deflation_params(min_trials=20)
    except Exception:  # noqa: BLE001
        deja = 20
    return int(deja) + n_variantes + 1


def _rendements(equity: list[float]) -> list[float]:
    return [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))
            if equity[i - 1] > 0]


def _ligne(nom: str, r: dict, sharpe: float, psr: float, dsr: float) -> str:
    esp = r["net"] / r["n"] if r["n"] else 0.0
    return (f"{nom:>12} | {r['n']:>5} | {r.get('profit_factor_sans_top5', 0):>5.2f} "
            f"| {r.get('expo', 0):>6.1%} | {sharpe:>6.2f} | {psr:>5.1%} | {dsr:>5.1%} "
            f"| {esp:>7.1f} | {r['net']:>9,.0f}")


def main() -> None:
    from packages.research.sharpe_diff import comparer
    risques = [float(a) for a in sys.argv[1:]] or RISQUES
    data, acmap, mode, n_reels, debut, fin = _donnees()
    print(f"\ndonnées : {len(data)} symboles · mode {mode} · {n_reels} à prix réels\n")
    if n_reels < 30:
        print("⚠️  AUCUNE base réelle branchée — ce banc ne décide de rien "
              "sur du synthétique.")
        return

    vix, prov = _vix(data, debut, fin)
    print(f"  empreinte : {empreinte(data, prov)}")
    n_essais = _essais(len(risques) + len(FRACTIONS_VOL))
    base = _run(data, acmap, 0.0, vix)
    rb = _rendements(base["equity"])
    s_base = comparer(rb, rb, periodes_par_an=252.0)["sharpe_base"]
    cols = ("dimension.", "trades", "PF-5", "expo", "Sharpe", "PSR", "DSR",
            "esp./tr", "net $")
    larg = (12, 5, 5, 6, 6, 5, 5, 7, 9)
    print(" | ".join(f"{c:>{w}}" for c, w in zip(cols, larg, strict=True)))
    print("-" * 84)
    print(_ligne("notionnel", base, s_base, *_psr_dsr(rb, n_essais)))

    for risque in risques:
        r = _run(data, acmap, risque, vix)
        # 252 : les rendements sont QUOTIDIENS. Le défaut de `comparer` est mensuel,
        # et l'oublier annualiserait le Sharpe par sqrt(12) au lieu de sqrt(252).
        rv = _rendements(r["equity"])
        d = comparer(rb, rv, periodes_par_an=252.0)
        if not d.get("disponible"):
            print(f"{'':>12} | {d.get('raison')}")
            continue
        print(_ligne(f"risque {risque:.1%}", r, d["sharpe_variante"],
                     *_psr_dsr(rv, n_essais)))
        print(f"{'':>12} | ΔSharpe {d['delta']:+.3f} · IC95 {d['ic95']} "
              f"· p = {d['p']:.4f} · {d['verdict'].upper()}")

    print(f"\nPSR = P(Sharpe vrai > 0). DSR = le même, seuil relevé pour {n_essais} "
          "essais : le maximum\nde N Sharpe bruités croît en sqrt(2 ln N), donc un "
          "beau chiffre obtenu après vingt\ntentatives ne vaut pas le même obtenu du "
          "premier coup. `esp./tr` = net / trades.")
    print("\nPF-5 = profit factor privé des cinq meilleurs trades ; sous 1,00 le "
          "résultat tient à\ncinq lignes. `t eff` corrige la dépendance entre trades "
          "qui se chevauchent.\n\n`t` MONTE MÉCANIQUEMENT AVEC LE NOMBRE DE TRADES "
          "(il vaut espérance/écart-type × sqrt(n)) :\nentre deux variantes de "
          "cardinalités différentes, il n'est pas comparable. Le seul\narbitre à "
          "l'échelle près est le Sharpe, et `expo` dit si les deux jouent bien le\n"
          "même niveau d'investissement.\n")


if __name__ == "__main__":
    main()
