"""Rendement PONDÉRÉ DANS LE TEMPS (TWR) — mesurer la performance, pas les virements.

Le problème. La performance d'un compte réel était calculée directement sur la valeur du compte :
`r = equity[t] / equity[t-1] - 1`. Un dépôt, un retrait ou un transfert entre comptes est alors
compté comme un GAIN ou une PERTE. C'est le défaut classique de mesure de performance, et il
n'est pas discret : il déplace le rendement total, le Sharpe et surtout le drawdown maximum.

La norme (GIPS) répond par le rendement pondéré dans le temps : on découpe la série à chaque
mouvement de trésorerie et on CHAÎNE les rendements des sous-périodes. Le résultat ne dépend
plus ni du montant ni de la date des versements — il mesure la gestion, pas l'alimentation.

Détection. Quand le courtier ne publie pas ses mouvements (cas de Bitmart, et d'Alpaca via
l'API utilisée ici), on les REPÈRE : un mouvement de trésorerie produit un saut sans commune
mesure avec l'agitation habituelle du compte. On compare donc chaque variation à un écart-type
ROBUSTE (MAD × 1,4826) — robuste au sens propre : les sauts eux-mêmes ne gonflent pas le seuil
qui doit les détecter, contrairement à un écart-type ordinaire.

Règle de prudence : dans le doute, on NE BOOKE PAS. Un saut inexpliqué est écarté du rendement
et signalé, jamais compté comme performance. Mieux vaut un rendement incomplet et déclaré qu'un
rendement faux et silencieux.
"""

from __future__ import annotations

import math

# Seuil de détection en écarts-types robustes. 5 sigma sur une loi normale ≈ 1 chance sur 1,7
# million par observation : au-delà, l'explication « marché » n'est plus crédible sur un compte
# de quelques dizaines de points. Volontairement conservateur — on préfère manquer un petit
# virement que confisquer une vraie journée de marché.
Z_DEFAUT = 5.0
# En deçà, la dispersion n'est pas estimable : on ne détecte rien plutôt que n'importe quoi.
MIN_POINTS = 10


def _returns(values: list[float]) -> list[float]:
    """Rendements simples successifs. Une valeur nulle ou négative rompt la chaîne (→ None)."""
    out: list[float] = []
    for prev, cur in zip(values, values[1:]):
        out.append(cur / prev - 1.0 if prev > 0 and cur > 0 else float("nan"))
    return out


def robust_sigma(returns: list[float]) -> float:
    """Écart-type ROBUSTE via l'écart absolu médian (MAD × 1,4826).

    1,4826 = 1 / Φ⁻¹(0,75) : le facteur qui rend le MAD comparable à un écart-type sous loi
    normale. On l'utilise parce qu'un écart-type ordinaire serait gonflé par les sauts mêmes
    qu'on cherche — le détecteur se saborderait.
    """
    r = [x for x in returns if x == x]
    if len(r) < 3:
        return 0.0
    r_tri = sorted(r)
    med = r_tri[len(r_tri) // 2]
    ecarts = sorted(abs(x - med) for x in r)
    mad = ecarts[len(ecarts) // 2]
    return 1.4826 * mad


def detect_flows(values: list[float], z: float = Z_DEFAUT) -> list[int]:
    """Indices des PAS (t → t+1) attribuables à un mouvement de trésorerie, pas au marché.

    Renvoie les indices i tels que le passage de values[i] à values[i+1] est jugé exogène.
    Liste vide si la série est trop courte ou sans dispersion mesurable : on ne devine pas.
    """
    if len(values) < MIN_POINTS:
        return []
    r = _returns(values)
    sigma = robust_sigma(r)
    if sigma <= 0:
        return []
    seuil = z * sigma
    return [i for i, x in enumerate(r) if x == x and abs(x) > seuil]


def twr(values: list[float], flows: list[int] | None = None) -> dict:
    """Rendement pondéré dans le temps : produit des sous-périodes, mouvements exclus.

    `flows` = indices des pas à neutraliser (détectés si non fourni). Le rendement des pas
    neutralisés n'est ni compté ni remplacé : la chaîne les enjambe, ce qui est exactement le
    traitement GIPS d'un versement.
    """
    if len(values) < 2:
        return {"available": False, "raison": "moins de deux points"}
    idx = set(detect_flows(values) if flows is None else flows)
    r = _returns(values)
    gardes = [x for i, x in enumerate(r) if i not in idx and x == x]
    if not gardes:
        return {"available": False, "raison": "aucune sous-période exploitable"}
    cumul = 1.0
    for x in gardes:
        cumul *= 1.0 + x
    brut = values[-1] / values[0] - 1.0 if values[0] > 0 else float("nan")
    return {
        "available": True,
        "total_return": cumul - 1.0,          # rendement de GESTION (hors versements)
        "raw_return": brut,                   # variation brute du compte (versements inclus)
        "returns": gardes,                    # sous-périodes retenues → Sharpe/maxDD honnêtes
        "n_flows": len(idx),
        "flows": sorted(idx),
        "n_periods": len(gardes),
    }


def flow_report(values: list[float], dates: list[str] | None = None,
                z: float = Z_DEFAUT) -> dict:
    """Rapport lisible : rendement corrigé, mouvements repérés, et de quoi juger sur pièces."""
    res = twr(values, None)
    if not res.get("available"):
        return {"available": False, "raison": res.get("raison")}
    r = _returns(values)
    sigma = robust_sigma(r)
    mouvements = []
    for i in res["flows"]:
        av, ap = values[i], values[i + 1]
        mouvements.append({
            "date": (dates[i + 1] if dates and i + 1 < len(dates) else None),
            "avant": round(av, 2), "apres": round(ap, 2),
            "montant": round(ap - av, 2),
            "variation": round(r[i], 4) if r[i] == r[i] else None,
            "sigmas": round(abs(r[i]) / sigma, 1) if sigma > 0 and r[i] == r[i] else None,
        })
    ecart = res["raw_return"] - res["total_return"]
    return {
        "available": True,
        "total_return": round(res["total_return"], 4),
        "raw_return": round(res["raw_return"], 4) if res["raw_return"] == res["raw_return"] else None,
        "ecart": round(ecart, 4) if ecart == ecart else None,
        "n_flows": res["n_flows"],
        "mouvements": mouvements,
        "sigma_robuste": round(sigma, 5),
        "vol_annualisee_robuste": round(sigma * math.sqrt(252), 4),
        "contamine": res["n_flows"] > 0,
        "note": ("Aucun mouvement de trésorerie détecté : la variation du compte est de la performance."
                 if res["n_flows"] == 0 else
                 f"{res['n_flows']} mouvement(s) de trésorerie neutralisé(s) — versements et retraits "
                 "ne sont ni des gains ni des pertes. Le rendement affiché mesure la gestion."),
    }
