"""Couche DÉCISION du screening : note pondérée (avec véto) et journal de décision.

Extrait d'`alpha_pipeline.py` (plafond de 400 lignes du dépôt). Deux responsabilités :

1. **`note_ponderee`** — répond à « et si un critère n'est pas rempli mais que la note
   globale est bonne ? ». Oui pour les critères GRADUELS (marge, croissance, cherté,
   momentum) : ce sont des degrés, et un excellent bilan compense une croissance moyenne.
   **Non** pour ce qui porte un risque de RUINE : au-delà du véto de levier, aucune note ne
   rachète une dette insoutenable. C'est la ligne que les desks ne franchissent pas — on
   compense de la performance, jamais de la solvabilité.

2. **`journal_decision`** — rend VISIBLE ce que le risk management a fait, et surtout ce
   qu'il a ÉVITÉ : positions écartées pour cause de doublon de corrélation, concentration
   réelle (nombre EFFECTIF de lignes, pas le compte), budget de risque de queue consommé.
   Sans ces lignes, le travail de risque est invisible et le robot paraît arbitraire.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.risk_metrics import cvar_historical


def expected_shortfall(returns, alpha: float = 0.95) -> float:
    """ES historique — perte moyenne dans les pires (1−alpha). Jamais de VaR gaussienne."""
    return float(cvar_historical(returns, alpha=alpha))


def _c01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


PONDERATIONS = {"qualite": 0.30, "solvabilite": 0.20, "valorisation": 0.30, "momentum": 0.20}


def note_ponderee(m: dict, val: dict | None, mom: dict | None,
                  s: Seuils) -> dict:
    """Note 0–1 où un critère manqué peut être COMPENSÉ — sauf véto de solvabilité.

    Répond à « et si un critère n'est pas rempli mais que la note globale est bonne ? ».
    Oui pour les critères GRADUELS (marge, croissance, cherté, momentum) : ce sont des
    degrés, et un excellent bilan compense une croissance moyenne. **Non** pour ce qui
    porte un risque de RUINE : au-delà de `debt_to_equity_veto`, aucune note ne rachète
    une dette insoutenable. C'est la ligne que les desks ne franchissent pas — on
    compense de la performance, jamais de la solvabilité.
    """
    marge, croiss = m.get("net_margin"), m.get("revenue_growth")
    de, pe = m.get("debt_to_equity"), m.get("price_to_earnings")
    q = []
    if marge is not None:
        q.append(_c01(marge / s.net_margin_min))
    if croiss is not None:
        q.append(_c01(croiss / s.revenue_growth_min))
    sous = {"qualite": float(np.mean(q)) if q else 0.0,
            "solvabilite": 1.0 if de is None else _c01(1.0 - de / max(1e-9, s.debt_to_equity_max)),
            "valorisation": 0.0, "momentum": 0.0}
    v = []
    if val and val.get("available") and not val.get("fragile"):
        v.append(_c01(val["marge_securite"] / s.marge_securite_min))
    if pe is not None:
        v.append(_c01(s.pe_max / pe))
    sous["valorisation"] = float(np.mean(v)) if v else 0.0
    if mom and mom.get("available"):
        sous["momentum"] = float(sum([bool(mom["au_dessus_ema50"]), bool(mom["tendance_haussiere"]),
                                      mom.get("volume_confirme") is not False]) / 3.0)
    note = sum(PONDERATIONS[k] * sous[k] for k in PONDERATIONS)
    veto, raison = False, ""
    if de is not None and de > s.debt_to_equity_veto:
        veto, raison = True, (f"VÉTO solvabilité : D/E {de:.2f} > {s.debt_to_equity_veto} — "
                              "aucune note ne compense un risque de ruine")
    return {"note": round(float(note), 4), "sous_notes": {k: round(v, 3) for k, v in sous.items()},
            "veto": veto, "raison_veto": raison,
            "compenses": [k for k, x in sous.items() if x < 0.5 and not veto]}


# ------------------------------------------------------------- journal de décision
def journal_decision(retenus: list[str], poids: dict[str, float],
                     prices: dict[str, dict], corr_max: float = 0.80) -> dict:
    """Rend VISIBLE ce que le risk management a fait — et surtout ce qu'il a ÉVITÉ.

    Trois lignes qu'un opérateur veut lire avant de valider un ordre :
      - quelles positions ont été écartées parce que trop corrélées à une déjà retenue ;
      - à quel point le portefeuille est concentré (nombre EFFECTIF de lignes, pas le compte) ;
      - combien de budget de risque de queue est consommé.
    Sans ces lignes, le travail de risque est invisible et le robot paraît arbitraire.
    """
    lignes: list[str] = []
    ecartes: list[dict] = []
    gardes = list(retenus)
    # 1. corrélation : on parcourt par poids décroissant, on écarte ce qui double une ligne
    ordre = sorted(gardes, key=lambda x: -poids.get(x, 0.0))
    conserves: list[str] = []
    for sym in ordre:
        r = np.asarray((prices.get(sym) or {}).get("returns", []), dtype=float)
        double = None
        for autre in conserves:
            ra = np.asarray((prices.get(autre) or {}).get("returns", []), dtype=float)
            n = min(r.size, ra.size)
            if n < 60:
                continue
            c = float(np.corrcoef(r[-n:], ra[-n:])[0, 1])
            if np.isfinite(c) and c > corr_max:
                double = (autre, c)
                break
        if double:
            ecartes.append({"symbole": sym, "correle_a": double[0], "correlation": round(double[1], 2)})
            lignes.append(f"{sym} écarté : corrélé à {double[1]:.0%} avec {double[0]} déjà retenu "
                          f"— deux fois le même pari, pas deux paris")
        else:
            conserves.append(sym)
    # 2. concentration
    w = {x: poids.get(x, 0.0) for x in conserves}
    total = sum(w.values())
    conc = None
    if total > 0:
        from packages.risk.limits import concentration_report
        parts = {k: v / total for k, v in w.items()}
        conc = concentration_report(parts)
        lignes.append(f"Concentration : {conc['effective_n']} lignes effectives pour "
                      f"{conc['n_positions']} positions ; la plus grosse pèse "
                      f"{conc['top_name_weight']:.0%} ({conc['top_name']})")
        for b in conc.get("breaches", []):
            lignes.append(f"Limite dépassée : {b['label']} à {b['weight']:.0%} "
                          f"(plafond {b['limit']:.0%})")
    # 3. budget de risque de queue consommé
    es_total = 0.0
    for x in conserves:
        r = (prices.get(x) or {}).get("returns")
        if r is not None and len(r) > 20:
            es_total += poids.get(x, 0.0) * expected_shortfall(r)
    if es_total > 0:
        lignes.append(f"Risque de queue : lors des 5 % de pires journées, le portefeuille perd "
                      f"en moyenne {es_total:.2%} — soit {round(es_total * 10000):,} € "
                      f"sur 10 000 €".replace(",", " "))
    return {"conserves": conserves, "ecartes_correlation": ecartes,
            "concentration": conc, "es_portefeuille": round(es_total, 5),
            "lignes": lignes}


