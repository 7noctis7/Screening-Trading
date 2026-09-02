#!/usr/bin/env python3
"""Quatre candidats, un seul protocole — avant d'en câbler un seul.

CE QUE CE BANC DÉCIDE, ET DANS QUEL ORDRE. Un candidat doit franchir DEUX portes, et la
première n'a rien à voir avec sa qualité propre :

  1. APPORTE-T-IL QUELQUE CHOSE DE NOUVEAU ? Le Sharpe d'une combinaison de N flux de
     Sharpe s et corrélation rho vaut s·sqrt(N/(1+(N-1)·rho)). Un flux corrélé à 0,7
     n'apporte quasi rien, quel que soit son Sharpe propre. La corrélation se lit donc
     AVANT le Sharpe.
  2. TIENT-IL DEBOUT SEUL ? Sharpe, PSR, et surtout DSR — déflaté du nombre d'essais,
     celui-ci inclus.

LES CANDIDATS. Trois sont pilotés par le prix et passent par le harnais commun ; le PEAD
est piloté par un ÉVÉNEMENT, ce qui en fait le seul structurellement orthogonal à la
tendance — et c'est aussi pour ça qu'il est le plus prometteur.

  · pead (proxy)      écart de cours exceptionnel = annonce ; on suit la dérive 21 jours
  · échec d'enchère   mèche de rejet sur volume, mesuré à phi ~ 0 du filtre existant
  · structure pivots  BOS/CHoCH — attendu redondant avec la tendance, on le vérifie
  · canal (IDWM)      cassure du plus-haut de canal = Donchian, la version testable des
                      « key levels » intraday/daily/weekly/monthly

RÉSERVE SUR LE PEAD. Le proxy détecte l'événement par le PRIX (gap exceptionnel), faute
de calendrier de résultats dans la base. C'est ce que fait déjà le blackout du preset.
La confirmation sur vraies dates passe par `scripts/backtest_earnings.py`, qui les
récupère chez yfinance — plus lent, mais c'est lui qui fait foi.

    python scripts/candidats_lab.py           # ~150 titres
    python scripts/candidats_lab.py 300
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FENETRE = 250
PAS = 5
SEUIL_GAP = 0.06                 # |variation d'un jour| au-delà = « annonce » (proxy)
DERIVE = 21                      # jours de dérive suivis après l'événement (PEAD)


def _signaux() -> dict:
    from packages.indicators.market_structure import echec_enchere, tendance
    from packages.research.breakout import channel_break

    def pead_proxy(b) -> bool:
        """Un gap haussier exceptionnel dans les `DERIVE` derniers jours → on suit."""
        for k in range(len(b) - DERIVE, len(b)):
            if k < 1:
                continue
            p0, p1 = float(b[k - 1].close), float(b[k].close)
            if p0 > 0 and (p1 / p0 - 1.0) > SEUIL_GAP:
                return True
        return False

    return {
        "pead (proxy gap)": pead_proxy,
        "échec d'enchère": lambda b: bool(echec_enchere(b, len(b) - 1).get("echec")),
        "structure pivots": lambda b: tendance(b, len(b) - 1) == "haussier",
        "canal / IDWM": lambda b: bool(
            channel_break([x.close for x in b], win=60)["break"]),
    }


def _stats(rends: list[float], n_essais: int) -> dict:
    import statistics as st

    from packages.portfolio.psr import psr_dsr_depuis_rendements
    if len(rends) < 60:
        return {}
    ec = st.pstdev(rends)
    d = psr_dsr_depuis_rendements(rends, n_trials=n_essais)
    return {"sharpe": (st.fmean(rends) / ec * (252 ** 0.5)) if ec > 0 else 0.0,
            "psr": d.get("psr"), "dsr": d.get("dsr")}


def _correlation(a: list[float], b: list[float]) -> float:
    import statistics as st
    m = min(len(a), len(b))
    if m < 60:
        return 0.0
    a, b = a[-m:], b[-m:]
    sa, sb = st.pstdev(a), st.pstdev(b)
    if sa <= 0 or sb <= 0:
        return 0.0
    ma, mb = st.fmean(a), st.fmean(b)
    return sum((a[i] - ma) * (b[i] - mb) for i in range(m)) / m / (sa * sb)


def main() -> None:
    from packages.research.flux_candidat import flux_quotidien
    from scripts.sizing_lab import (
        _donnees,
        _essais,
        _rendements,
        _run,
        _vix,
        empreinte,
    )

    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    data, acmap, mode, n_reels, debut, fin = _donnees()
    if n_reels < 30:
        print("⚠️  Aucune base réelle branchée — ce banc ne décide de rien.")
        return
    data = {s: data[s] for s in sorted(data)[:n_max]}
    signaux = _signaux()
    n_essais = _essais(len(signaux))

    vix, prov = _vix(data, debut, fin)
    print(f"\nmode {mode} · décision tous les {PAS} jours")
    print(f"empreinte : {empreinte(data, prov)}")
    ref = _run(data, acmap, 0.005, vix)
    r_ref = _rendements(ref["equity"])
    s_ref = _stats(r_ref, n_essais)
    print(f"  {'candidat':<20} {'lignes':>7} {'Sharpe':>7} {'PSR':>6} {'DSR':>6} "
          f"{'rho':>6} {'50/50':>7}  verdict")
    print("  " + "-" * 78)
    print(f"  {'PRODUCTION':<20} {'—':>7} {s_ref['sharpe']:>7.2f} {s_ref['psr']:>5.0%} "
          f"{s_ref['dsr']:>5.0%} {'—':>6} {'—':>7}")

    for nom, fn in signaux.items():
        f = flux_quotidien(data, fn, fenetre=FENETRE, pas=PAS)
        if not f.get("available"):
            print(f"  {nom:<20} {f.get('motif', 'indisponible')}")
            continue
        st_c = _stats(f["rendements"], n_essais)
        rho = _correlation(r_ref, f["rendements"])
        # Sharpe d'un 50/50 : (s0+s)/2 / sqrt((1+rho)/2) en variances égales.
        duo = (s_ref["sharpe"] + st_c["sharpe"]) / 2 / max(((1 + rho) / 2) ** 0.5, 1e-9)
        gagne = duo > s_ref["sharpe"] + 0.27
        verdict = ("redondant" if abs(rho) >= 0.5
                   else ("APPORTE" if gagne else "sous le seuil"))
        print(f"  {nom:<20} {f['lignes_moyen']:>7.1f} {st_c['sharpe']:>7.2f} "
              f"{st_c['psr']:>5.0%} {st_c['dsr']:>5.0%} {rho:>+6.2f} {duo:>7.2f}  "
              f"{verdict}")

    print("\n  rho = corrélation des rendements quotidiens au flux de PRODUCTION.")
    print("  « 50/50 » = Sharpe d'un mélange à parts égales, variances comparables.")
    print("  Un candidat ne vaut d'être construit que s'il dépasse la production de")
    print("  plus que le seuil détectable (±0.27) — sinon on ne le prouvera jamais.")
    print(f"  DSR déflaté de {n_essais} essais, ceux de ce banc inclus.\n")


if __name__ == "__main__":
    main()
