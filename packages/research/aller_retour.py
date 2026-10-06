"""Un ALLER-RETOUR, défini une fois, et son espérance nette (frais et impact).

DÉFINITION. Un aller-retour est une quantité achetée par un ordre EXÉCUTÉ — donc un
écart qui a franchi la bande d'inaction et le plancher (`rebalance_plan.decider`) — puis
revendue par un ordre exécuté. Il va du prix d'exécution d'achat au prix d'exécution de
vente. Appariement FIFO en QUANTITÉ, ligne par ligne : une vente partielle ferme la
fraction la plus ancienne. Une détention n'est pas un aller-retour ; une quantité encore
détenue à la fin n'en est pas un non plus (comptée à part, jamais valorisée en latent).

RENDEMENT NET d'un aller-retour (fraction du notionnel d'achat) :

    brut  = px_vente / px_achat − 1
    net   = brut − coût_achat − coût_vente − impact_achat − impact_vente

`coût_*` est le coût par côté appliqué à l'exécution (barème `CostModel`, demi
aller-retour). `impact_*` vient de `packages.execution.impact` (loi en racine carrée) ;
son coefficient Y n'est PAS calibré sur le TCA réel : il est toujours fourni par
l'appelant et publié avec le résultat.

ESPÉRANCE. Moyenne pondérée par le notionnel (le livre encaisse des dollars, pas des
lots) et moyenne simple ; intervalle à 95 % par bootstrap sur les allers-retours.
Ces allers-retours ne sont pas indépendants (même date, même marché) : l'intervalle est
optimiste, et le rapport le dit.
"""

from __future__ import annotations

from collections import deque

import numpy as np

N_MIN = 30                    # sous 30 allers-retours, aucune espérance publiée


def apparier(executions: list[dict]) -> tuple[list[dict], int]:
    """Allers-retours FIFO depuis [{jour, sym, montant, px, cout}] triés par date.

    Renvoie (allers-retours, nombre de lots encore ouverts à la fin)."""
    files: dict[str, deque] = {}
    sortie: list[dict] = []
    for e in executions:
        px, mt = float(e["px"]), float(e["montant"])
        if px <= 0 or mt == 0:
            continue
        q = abs(mt) / px
        if mt > 0:
            files.setdefault(e["sym"], deque()).append(
                {"q": q, "px": px, "cout": float(e["cout"]), "jour": e["jour"]})
            continue
        file = files.get(e["sym"]) or deque()
        while q > 1e-12 and file:
            lot = file[0]
            pris = min(q, lot["q"])
            sortie.append({"sym": e["sym"], "achat": lot["jour"], "vente": e["jour"],
                           "q": pris, "px_achat": lot["px"], "px_vente": px,
                           "cout_achat": lot["cout"], "cout_vente": float(e["cout"]),
                           "notionnel": pris * lot["px"]})
            lot["q"] -= pris
            q -= pris
            if lot["q"] <= 1e-12:
                file.popleft()
    ouverts = sum(len(f) for f in files.values())
    return sortie, ouverts


def rendement_net(ar: dict, impact_achat: float = 0.0,
                  impact_vente: float = 0.0) -> float:
    """Rendement net d'un aller-retour, en fraction du notionnel d'achat."""
    brut = ar["px_vente"] / ar["px_achat"] - 1.0
    return brut - ar["cout_achat"] - ar["cout_vente"] - impact_achat - impact_vente


def _moyenne_ponderee(r: np.ndarray, w: np.ndarray) -> float:
    return float((r * w).sum() / w.sum()) if w.sum() > 0 else float("nan")


def esperance(nets: list[float], notionnels: list[float], n_boot: int = 2000,
              graine: int = 0) -> dict:
    """Espérance nette par aller-retour (pondérée et simple), IC 95 % par bootstrap."""
    r, w = np.asarray(nets, float), np.asarray(notionnels, float)
    if r.size < N_MIN:
        return {"available": False, "status": "UNCALIBRATED", "n": int(r.size),
                "motif": f"{r.size} aller(s)-retour(s) < {N_MIN}"}
    rng = np.random.default_rng(graine)
    idx = rng.integers(0, r.size, size=(n_boot, r.size))
    boot = (r[idx] * w[idx]).sum(axis=1) / w[idx].sum(axis=1)
    gains, pertes = r[r > 0], r[r <= 0]
    return {"available": True, "n": int(r.size),
            "esperance_ponderee": _moyenne_ponderee(r, w),
            "ic95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "esperance_simple": float(r.mean()),
            "taux_gain": float((r > 0).mean()),
            "gain_moyen": float(gains.mean()) if gains.size else None,
            "perte_moyenne": float(pertes.mean()) if pertes.size else None,
            "gain_net_livre": float((r * w).sum())}


def duree_jours(ar: dict) -> int:
    """Détention calendaire d'un aller-retour, en jours."""
    from datetime import date
    return (date.fromisoformat(ar["vente"]) - date.fromisoformat(ar["achat"])).days
