"""Grille pré-enregistrée, classement déflaté et période cachée à lecture unique.

Le classement de centaines de règles sur un même historique est une machine à faux
positifs : le premier est, en espérance, un chanceux. Trois verrous :

1. **Empreinte** — la grille est figée par un sha256 AVANT tout calcul ; changer un
   paramètre après avoir vu les résultats produit une autre empreinte, donc un autre essai.
2. **Déflation** — chaque scénario compte dans N (DSR de Bailey-López de Prado), et la
   probabilité de surapprentissage (PBO, CSCV) mesure si le champion en échantillon reste
   au-dessus de la médiane hors échantillon.
3. **Période cachée** — la fin de l'historique n'est lue QU'UNE fois par empreinte, pour
   1 à 3 scénarios choisis sur le classement en échantillon. Une seconde lecture lève.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REGISTRE = Path("research/holdout_registre.jsonl")
UNIVERS_MONO = ("qqq", "btc")        # un seul actif : sélection et pondération sans objet


def empreinte(grille: dict) -> str:
    """sha256 du JSON canonique (clés triées) : indépendant de l'ordre d'écriture."""
    brut = json.dumps(grille, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


def _combinaisons(grille: dict, univers: str) -> list[tuple[str, str]]:
    if univers in UNIVERS_MONO:
        return [("tout", "egal")]
    # « tout » × ERC : une matrice de covariance sur des centaines de titres et 63 barres
    # est singulière — le scénario ne mesurerait que le conditionnement numérique.
    return [(s, p) for s in grille["selections"] for p in grille["ponderations"]
            if not (s == "tout" and p == "erc")]


def scenarios(grille: dict) -> list[dict]:
    """Expansion déterministe de la grille en scénarios identifiés."""
    out = []
    for u in grille["univers"]:
        for sel, pond in _combinaisons(grille, u):
            for ov in grille["overlays"]:
                for nom_pas, pas in grille["pas"].items():
                    out.append({"id": f"{u}|{sel}|{pond}|{ov}|{nom_pas}", "univers": u,
                                "selection": sel, "ponderation": pond, "overlay": ov,
                                "pas": int(pas), "nom_pas": nom_pas,
                                "top_k": int(grille.get("top_k", 10))})
    return out


def _moments(r: np.ndarray) -> tuple[float, float, float]:
    sd = r.std(ddof=1)
    if sd <= 0:
        return 0.0, 0.0, 3.0
    z = (r - r.mean()) / sd
    return float(r.mean() / sd), float((z ** 3).mean()), float((z ** 4).mean())


def _stats(r: np.ndarray, par_an: float) -> dict:
    courbe = np.cumprod(1.0 + r)
    annees = max(r.size / par_an, 1e-9)
    pic = np.maximum.accumulate(np.concatenate([[1.0], courbe]))
    dd = float((np.concatenate([[1.0], courbe]) / pic - 1.0).min())
    return {"cagr": float(courbe[-1] ** (1.0 / annees) - 1.0) if courbe[-1] > 0 else -1.0,
            "vol": float(r.std(ddof=1) * np.sqrt(par_an)), "max_dd": dd}


def classer(lignes: list[dict], R: np.ndarray, par_an: float,
            n_anterieurs: int = 0) -> tuple[list[dict], dict]:
    """Classe les scénarios (colonnes de R, T×N) par Sharpe, avec DSR et PBO.

    N du DSR = scénarios de cette grille + essais antérieurs du programme ; la dispersion
    des Sharpe est celle MESURÉE entre scénarios (même périodicité, par barre)."""
    from packages.portfolio.pbo import pbo_cscv
    from packages.portfolio.psr import deflated_sharpe_ratio
    R = np.asarray(R, float)
    mom = [_moments(R[:, j]) for j in range(R.shape[1])]
    srs = np.array([m[0] for m in mom])
    sr_std = max(float(srs.std(ddof=1)), 1e-9) if srs.size > 1 else None
    n_essais = R.shape[1] + int(n_anterieurs)
    out = []
    for j, ligne in enumerate(lignes):
        sr, sk, ku = mom[j]
        out.append({**ligne, **_stats(R[:, j], par_an),
                    "sharpe": round(sr * np.sqrt(par_an), 4),
                    "dsr": deflated_sharpe_ratio(sr, R.shape[0], n_essais, sk, ku,
                                                 sr_std=sr_std)})
    out.sort(key=lambda d: d["sharpe"], reverse=True)
    for k, d in enumerate(out, 1):
        d["rang"] = k
    return out, pbo_cscv(R)


def _lire(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    out = []
    for brut in chemin.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(brut))
        except json.JSONDecodeError:
            continue
    return out


def holdout_deja_lu(hash_grille: str, chemin: str | Path = REGISTRE) -> bool:
    return any(r.get("empreinte") == hash_grille for r in _lire(Path(chemin)))


def consommer_holdout(hash_grille: str, ids: list[str],
                      chemin: str | Path = REGISTRE) -> None:
    """Inscrit la lecture de la période cachée. Une seconde lecture est REFUSÉE."""
    p = Path(chemin)
    if holdout_deja_lu(hash_grille, p):
        raise RuntimeError(f"période cachée déjà lue pour la grille {hash_grille[:8]} — "
                           "une seconde lecture la transformerait en échantillon d'apprentissage")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"empreinte": hash_grille, "scenarios": list(ids),
                             "lu_le": datetime.now(UTC).isoformat(timespec="seconds")},
                            ensure_ascii=False) + "\n")
