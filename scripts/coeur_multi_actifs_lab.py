#!/usr/bin/env python3
"""Cœur multi-actifs (QQQ + obligations longues + or) contre le cœur QQQ de production.

CE QUE CE BANC TESTE, ET CE QU'IL NE TESTE PAS. Il ne teste pas « plus de titres » : la
taille du cœur reste 50 %, exactement comme en production. Il ne change QUE la
composition du cœur. Tout écart mesuré est donc imputable à la corrélation, à rien
d'autre.

RÈGLE D'ACCEPTATION, ÉCRITE AVANT LE RUN (comme pour le suiveur, le 02/09). Le cœur
multi-actifs remplace le cœur QQQ en production SI ET SEULEMENT SI, sur les MÊMES dates
et contre le mélange de production :
  (a) le test apparié de Jobson-Korkie/Memmel donne ΔSharpe > 0 avec p < 0,05 ;  ET
  (b) le maxDD n'est pas dégradé ;                                                ET
  (c) le DSR, déflaté du nombre d'essais RÉELS (ce banc inclus), est >= 50 %.
Si (a) échoue, on ne bouge pas — quel que soit le CAGR affiché. Si (a) passe et (b)
échoue, on ne bouge pas non plus : acheter du Sharpe avec un drawdown plus profond
contredit la raison même de construire ce cœur.

ISSUE SECONDAIRE, DÉCLARÉE ELLE AUSSI D'AVANCE. Si le ΔSharpe est indiscernable mais que
le maxDD s'améliore de plus de 5 points absolus, ce n'est PAS un feu vert automatique :
c'est « réduction du risque à Sharpe égal », remonté tel quel pour décision humaine.

QUATRE ESSAIS, PAS UN DE PLUS : trois pondérations fixes + une inverse-vol. Ils sont
figés dans `packages/backtest/coeur_multi_actifs.PANIERS` et comptés dans la déflation.

    export QUANT_PRICE_DB=/chemin/YAHOO.db
    python scripts/coeur_multi_actifs_lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PART_COEUR = 0.50          # identique à la production — on ne change QUE la composition
SEUIL_DSR = 0.50
SEUIL_DD_SECONDAIRE = 0.05


def _rends(eq: list[float]) -> list[float]:
    return [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]


def _rends_axe(courbe: list, n: int) -> list[float]:
    """Rendements sur l'axe COMPLET : 0.0 là où la courbe n'existe pas encore.

    Les zéros ne sont jamais mesurés : la fenêtre commune du tableau commence après eux.
    """
    out = [0.0] * n
    for i in range(1, min(len(courbe), n)):
        a, b = courbe[i - 1], courbe[i]
        if a and b and a > 0:
            out[i] = b / a - 1.0
    return out


def _equity(rends: list[float], i0: int, base: float = 100.0) -> list[float]:
    eq = [base]
    for i in range(i0, len(rends)):
        eq.append(eq[-1] * (1.0 + rends[i]))
    return eq


def _stats(eq: list[float], n_essais: int) -> dict:
    from packages.backtest.index_core import _stats as kpis
    from packages.portfolio.psr import psr_dsr_depuis_rendements
    st = dict(kpis(eq))
    d = psr_dsr_depuis_rendements(_rends(eq), n_trials=n_essais)
    if d.get("available"):
        st["psr"], st["dsr"] = d["psr"], d["dsr"]
    return st


def _capm(a: list[float], b: list[float]) -> dict:
    """Alpha annualisé et t(alpha) de `a` contre `b`, séries DÉJÀ appariées."""
    import math
    m = len(a)
    if m < 30 or len(b) != m:
        return {}
    ma, mb = sum(a) / m, sum(b) / m
    var_b = sum((x - mb) ** 2 for x in b) / (m - 1)
    if var_b <= 0:
        return {}
    beta = sum((a[i] - ma) * (b[i] - mb) for i in range(m)) / (m - 1) / var_b
    alpha_j = ma - beta * mb
    resid = [a[i] - alpha_j - beta * b[i] for i in range(m)]
    s2 = sum(r * r for r in resid) / max(m - 2, 1)
    se = math.sqrt(s2 * (1.0 / m + mb * mb / ((m - 1) * var_b)))
    return {"alpha": alpha_j * 252, "beta": beta,
            "t": (alpha_j / se) if se > 0 else 0.0}


def _essais(variantes: int) -> int:
    """Essais RÉELS du registre + les variantes de ce banc. Le comptage voyage
    avec le chiffre."""
    try:
        from packages.research.ledger import deflation_params
        deja, _ = deflation_params(min_trials=20)
    except Exception:  # noqa: BLE001
        deja = 20
    return int(deja) + variantes


def _ligne(nom: str, st: dict, cap: dict | None, test: dict | None) -> None:
    def _p(x):
        return "  —" if x is None else f"{x*100:3.0f}%"
    cap = cap or {}
    t = test or {}
    delta = f"{t['delta']:+.2f}" if t.get("disponible") else "   —"
    p = f"{t['p']:.3f}" if t.get("disponible") else "  —"
    print(f"  {nom:<22} {st.get('cagr',0)*100:6.1f}% {st.get('sharpe',0):6.2f} "
          f"{st.get('sortino',0):7.2f} {st.get('max_drawdown',0)*100:7.1f}% "
          f"{_p(st.get('psr')):>5s} {_p(st.get('dsr')):>5s} "
          f"{cap.get('alpha',0)*100:6.1f}% {cap.get('t',0):6.2f} {delta:>7s} {p:>6s}")


def _series(snap: dict) -> tuple[dict, list[float], list[str], list[float]]:
    cur = snap.get("index_core_curves", {})
    div = {s: v for s, v in (cur.get("diversifiants") or {}).items()
           if any(x for x in v)}
    return (div, list(cur.get("preset", [])), list(cur.get("dates", [])),
            list(cur.get("qqq", [])))


def _fenetre_commune(coeurs: dict, n: int) -> int:
    """Départ COMMUN à toutes les variantes. Une seule fenêtre pour tout le tableau.

    Sans cela, chaque ligne porterait sur un échantillon différent et le lecteur ferait
    la soustraction — l'erreur exacte qui a fait lire « +0,39 » là où le test disait p =
    0,39.
    """
    departs = [c["depart"] for c in coeurs.values() if c.get("available")]
    return max(departs) if departs else n


def _variantes(div: dict) -> dict:
    from packages.backtest.coeur_multi_actifs import PANIERS, coeur_equity
    out = {}
    for nom, panier in PANIERS.items():
        poids = {s: w for s, w in panier if s in div}
        if len(poids) < len(panier):
            continue
        out[f"multi {nom}"] = coeur_equity({s: div[s] for s in poids}, poids)
    if len(div) >= 3:
        out["multi inverse-vol"] = coeur_equity(div, None, inverse_vol=True)
    return out


def main() -> None:
    print(__doc__.split("    export")[0].rstrip())
    print("\nConstruction du snapshot (mesure de production réelle)… ~30-60 s\n")
    from apps.api.snapshot import build_snapshot
    from packages.backtest.coeur_multi_actifs import SYMBOLES, correlations
    from packages.research.sharpe_diff import comparer

    snap = build_snapshot()
    div, preset, dates, qqq_idx = _series(snap)
    if not preset or len(preset) < 200:
        print("Preset indisponible — rien à mesurer.")
        return
    manquants = [s for s in SYMBOLES if s not in div]
    if manquants:
        print(f"⛔ Diversifiants absents de la base : {', '.join(manquants)}.")
        print("   Cœur multi-actifs non mesurable — UNCALIBRATED, on ne conclut pas.")
        return
    n = len(preset)
    pr = _rends_axe(preset, n)
    coeurs = _variantes(div)
    coeurs["contrôle QQQ ETF"] = {"available": True, "equity": div["QQQ"],
                                  "depart": next(i for i, v in enumerate(div["QQQ"])
                                                 if v)}
    i0 = _fenetre_commune(coeurs, n)
    if n - i0 < 250:
        print(f"⛔ Fenêtre commune de {n - i0} séances — trop courte.")
        return
    n_essais = _essais(len(coeurs) - 1)      # le contrôle n'est pas un candidat
    print(f"Fenêtre commune : {dates[i0]} → {dates[-1]} ({n - i0} séances) · "
          f"part de cœur {PART_COEUR:.0%} · {n_essais} essais pour la déflation")
    rho = correlations({s: div[s] for s in SYMBOLES}, i0)
    print("Corrélations quotidiennes (elles se lisent AVANT le Sharpe) : "
          + " · ".join(f"{k} {v:+.2f}" for k, v in sorted(rho.items())))

    # Référence = mélange de PRODUCTION, mesuré sur la MÊME fenêtre.
    from packages.backtest.index_core import blend_equity
    prod_eq, _ = blend_equity(preset, qqq_idx, PART_COEUR)
    prod_r = _rends(prod_eq)[-(n - i0 - 1):] if prod_eq else []
    ref = _equity(prod_r, 0)
    print(f"\n  {'variante':<22} {'CAGR':>7} {'Sharpe':>6} {'Sortino':>7} {'maxDD':>8} "
          f"{'PSR':>5} {'DSR':>5} {'alpha':>7} {'t(α)':>6} {'ΔSh':>7} {'p':>6}")
    print("  " + "-" * 96)
    _ligne("PRODUCTION 50% QQQ", _stats(ref, n_essais), None, None)

    resultats = {}
    for nom, c in sorted(coeurs.items()):
        if not c.get("available"):
            print(f"  {nom:<22} {c.get('motif', 'indisponible')}")
            continue
        cr = _rends_axe([x if x is not None else 0.0 for x in c["equity"]], n)
        br = [PART_COEUR * cr[i] + (1 - PART_COEUR) * pr[i] for i in range(i0 + 1, n)]
        eq = _equity(br, 0)
        st = _stats(eq, n_essais)
        apparie = len(prod_r) == len(br)
        test = comparer(prod_r, br, periodes_par_an=252.0) if apparie else {}
        _ligne(nom, st, _capm(br, prod_r) if apparie else {}, test)
        resultats[nom] = (st, test)
    _verdict(resultats, _stats(ref, n_essais))


def _verdict(resultats: dict, ref: dict) -> None:
    """La règle écrite en tête de fichier, appliquée telle quelle — sans l'assouplir."""
    print("\n  RÈGLE (écrite avant le run) : (a) ΔSharpe > 0 avec p < 0,05, "
          "(b) maxDD non dégradé, (c) DSR ≥ 50 %.")
    retenus, second = [], []
    for nom, (st, test) in sorted(resultats.items()):
        if nom.startswith("contrôle"):
            continue
        a = bool(test.get("disponible")) and test["delta"] > 0 and test["p"] < 0.05
        b = st.get("max_drawdown", -1) >= ref.get("max_drawdown", -1)
        c = st.get("dsr", 0.0) >= SEUIL_DSR
        pire = st.get("max_drawdown", -1) - ref.get("max_drawdown", -1)
        if a and b and c:
            retenus.append(nom)
        elif b and pire > SEUIL_DD_SECONDAIRE:
            second.append((nom, pire))
    if retenus:
        noms = ", ".join(retenus)
        print(f"  → RETENU(S) : {noms}. À confirmer hors échantillon avant "
              "de toucher à QUANT_CORE_SPEC.")
    else:
        print("  → AUCUNE variante ne passe la règle. Le cœur QQQ reste en production.")
    for nom, gain in second:
        print(f"    · {nom} : maxDD amélioré de {gain*100:.1f} pts à Sharpe"
              " indiscernable — réduction du risque, PAS un feu vert automatique.")
    print("\n  ⚠️ Rééq. mensuel du cœur, coût 5 bps sur le notionnel échangé ; le"
          " cœur QQQ, lui, ne paie AUCUN rééquilibrage → la comparaison est"
          " défavorable au nouveau venu.")


if __name__ == "__main__":
    main()
