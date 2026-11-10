"""Un essai FIGÉ de classement, de la mesure au verdict : IC apparié → portefeuille → gate.

Assemble, sans rien réimplémenter, ce que l'essai `config/essais/…` a déclaré AVANT la
mesure : l'IC de chaque variante face au témoin (`labo_classement`), le portefeuille net
de coûts de la variante principale (`portefeuille_classement`), puis les quatre étages du
gate — placebo, DSR (essais lus au registre par `verdict_hors_echantillon`), PBO sur les
variantes, sabotage. Le verdict applique la règle écrite dans l'essai, à deux niveaux :
FACTEUR (écart d'IC apparié) et STRATÉGIE (gate complet).

Chaque refus est publié avec le Sharpe que la porte exigeait (`puissance_gate`) : sans ce
nombre, « rejeté » ne distingue pas un effet absent d'un effet que l'instrument ne peut pas
voir sur cet historique.

STATUT : CANDIDATE. Fonctions pures sur un panneau ; les entrées-sorties (base de prix,
registre, fichier de résultat) sont dans `scripts/labo_momentum_residuel.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from packages.research.ic_classement import resume_horizon
from packages.research.labo_classement import (
    Classement,
    classement_momentum,
    classement_placebo,
    classement_residuel,
    ecart_apparie,
    lignes,
    sur_coupe_commune,
)
from packages.research.portefeuille_classement import (
    decisions,
    episodes,
    simuler,
    statistiques_episodes,
)

STATUT = "CANDIDATE"
SEANCES_PAR_AN = 252
N_JOURS_MIN = 250            # sous un an de rendements actifs, aucun verdict de stratégie


def variantes(essai: dict[str, Any]) -> list[dict[str, Any]]:
    return [essai["variante_principale"], *essai.get("voisines", [])]


def nom_variante(v: dict[str, Any]) -> str:
    return f"e{v['estimation']}_{'std' if v['standardise'] else 'brut'}"


def debut_commun(essai: dict[str, Any]) -> int:
    """Premier index mesurable pour TOUTES les variantes : elles partagent les dates."""
    return int(max(v["estimation"] for v in variantes(essai)))


def memoriser(classement: Classement) -> Classement:
    """Le même classement, calculé une seule fois par date (placebo : 500 relectures)."""
    cache: dict[int, np.ndarray | None] = {}

    def score(pan: dict[str, Any], t: int) -> np.ndarray | None:
        if t not in cache:
            cache[t] = classement(pan, t)
        return cache[t]
    return score


def _candidat(v: dict[str, Any]) -> Classement:
    return memoriser(classement_residuel(v["estimation"], v["formation"], v["saut"],
                                         v["standardise"]))


def _temoin(essai: dict[str, Any]) -> Classement:
    return memoriser(classement_momentum(essai["temoin"]["momentum"],
                                         essai["temoin"]["saut"]))


def mesurer_ic(pan: dict[str, Any], essai: dict[str, Any], n_nulles: int = 2000) -> dict[str, Any]:
    """{« variante:hN » : {candidat, ecart, compteurs}, « temoin:hN » : …}, pas = horizon."""
    debut = debut_commun(essai)
    out: dict[str, dict[str, Any]] = {}
    for h in essai["horizons_seances"]:
        lt, _ = lignes(pan, _temoin(essai), h, h, debut)
        out[f"temoin:h{h}"] = resume_horizon(lt, h, h, n_nulles)
        for v in variantes(essai):
            # Écart apparié : les DEUX IC sur la même coupe (titres classés par les deux).
            cand, tem = _candidat(v), _temoin(essai)
            lc, compteurs = lignes(pan, sur_coupe_commune(cand, tem), h, h, debut)
            lt_commun, _ = lignes(pan, sur_coupe_commune(tem, cand), h, h, debut)
            out[f"{nom_variante(v)}:h{h}"] = {
                "candidat": resume_horizon(lc, h, h, n_nulles),
                "ecart": ecart_apparie(lc, lt_commun, n_nulles), "compteurs": compteurs}
    return out


def rendements(pan: dict[str, Any], classement: Classement, essai: dict[str, Any],
               couts: np.ndarray | float) -> dict[str, Any]:
    """Portefeuille top-k net, univers de la même coupe, rendement actif et compteurs."""
    decs, sautees = decisions(pan, classement, essai["cadence_seances"],
                              debut_commun(essai), essai["top_k"])
    if not decs:
        return {"available": False, "decisions": 0, "decisions_sautees": sautees}
    livre = simuler(pan, decs, "cols", couts)
    univers = simuler(pan, decs, "coupe", 0.0)
    nets, compteurs = episodes(pan, decs, couts)
    return {"available": True, "jours": livre["jours"], "livre": livre["r"],
            "actif": livre["r"] - univers["r"],
            "rotation_par_jour": livre["rotation_par_jour"], "episodes": nets,
            "compteurs": {"decisions": len(decs), "decisions_sautees": sautees,
                          "rotation_mediane": float(np.median(livre["rotations"])),
                          "barres_manquantes": livre["barres_manquantes"],
                          "ordres_non_executables": livre["ordres_non_executables"],
                          **compteurs}}


def _sharpe(r: np.ndarray) -> float:
    sd = float(r.std(ddof=1)) if r.size > 1 else 0.0
    return float(r.mean() / sd) if sd > 0 else 0.0


def placebo(pan: dict[str, Any], classement: Classement, essai: dict[str, Any], couts: np.ndarray | float,
            sharpe_observe: float) -> dict[str, Any]:
    """p = part des sélections AU HASARD (même coupe) dont le Sharpe actif ≥ l'observé."""
    tirages = int(essai["tirages_placebo"])
    nuls = np.asarray([
        _sharpe(rendements(pan, classement_placebo(classement, g), essai, couts)["actif"])
        for g in range(tirages)])
    return {"tirages": tirages, "sharpe_placebo_p95": float(np.quantile(nuls, 0.95)),
            "p": float((1 + (nuls >= sharpe_observe).sum()) / (1 + tirages))}


def pbo_variantes(pan: dict[str, Any], essai: dict[str, Any], couts: np.ndarray | float) -> dict[str, Any]:
    """PBO (CSCV) sur les rendements actifs des variantes, alignés par date."""
    from packages.portfolio.pbo import pbo_cscv
    series = [rendements(pan, _candidat(v), essai, couts) for v in variantes(essai)]
    if not all(s["available"] for s in series):
        return {"available": False, "reason": "une variante n'a aucune décision"}
    communs = sorted(set.intersection(*(set(s["jours"]) for s in series)))
    rang = {j: i for i, j in enumerate(communs)}
    perf = np.zeros((len(communs), len(series)))
    for k, s in enumerate(series):
        for j, x in zip(s["jours"], s["actif"], strict=True):
            if j in rang:
                perf[rang[j], k] = x
    return pbo_cscv(perf)


def gate(actif: np.ndarray, pbo: float | None, placebo_p: float | None,
         chemin_ledger: str | Path | None = None) -> dict[str, Any]:
    """Les étages placebo, DSR et PBO sur la partie HORS ÉCHANTILLON du rendement actif.

    Le nombre d'essais vient du registre (`verdict_hors_echantillon`) — jamais d'ici."""
    from packages.research.gate import DSR_MIN, verdict_hors_echantillon
    from packages.research.protocole_oos import SEUIL_DSR, partitionner
    from packages.research.puissance_gate import sharpe_annuel_minimal
    if actif.size < N_JOURS_MIN:
        return {"available": False, "status": "UNCALIBRATED", "n_jours": int(actif.size)}
    oos = actif[partitionner(actif.size).fin_is:]
    sd = float(oos.std(ddof=1))
    centre = oos - oos.mean()
    v = verdict_hors_echantillon(
        sharpe_oos=_sharpe(oos), n_obs_oos=int(oos.size), pbo=pbo, placebo_p=placebo_p,
        edge=float(oos.mean() * SEANCES_PAR_AN), chemin_ledger=chemin_ledger,
        skew=float((centre ** 3).mean() / sd ** 3) if sd > 0 else 0.0,
        kurtosis=float((centre ** 4).mean() / sd ** 4) if sd > 0 else 3.0)
    annees = oos.size / SEANCES_PAR_AN
    return {"available": True, **v, "n_jours_oos": int(oos.size),
            "sharpe_oos_annualise": _sharpe(oos) * float(np.sqrt(SEANCES_PAR_AN)),
            "sharpe_exige_promouvable": sharpe_annuel_minimal(annees, v["n_essais"], DSR_MIN),
            "sharpe_exige_deployable": sharpe_annuel_minimal(annees, v["n_essais"],
                                                             SEUIL_DSR)}


def contre_temoin(candidat: dict[str, Any], temoin: dict[str, Any], essai: dict[str, Any]) -> dict[str, Any]:
    """Top-k candidat − top-k témoin, nets, par date commune ; IC 95 % par blocs."""
    from packages.research.melange_meme_risque import _bootstrap_blocs
    ref = dict(zip(temoin["jours"], temoin["livre"], strict=True))
    d = np.asarray([x - ref[j] for j, x in zip(candidat["jours"], candidat["livre"],
                                               strict=True) if j in ref])
    if d.size < N_JOURS_MIN:
        return {"available": False, "status": "UNCALIBRATED", "n_jours": int(d.size)}
    b = essai["bootstrap"]
    boot = _bootstrap_blocs(d, int(b["tirages"]), int(b["bloc_seances"]), 0) * SEANCES_PAR_AN
    return {"available": True, "n_jours": int(d.size),
            "ecart_annualise": float(d.mean() * SEANCES_PAR_AN),
            "ic95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}


def decision(ic: dict[str, Any], essai: dict[str, Any], strategie: dict[str, Any], sabotage: dict[str, Any],
             face_temoin: dict[str, Any]) -> dict[str, Any]:
    """La règle de l'essai, appliquée telle qu'écrite. Deux niveaux, motifs explicites."""
    nom = nom_variante(essai["variante_principale"])
    hp = essai["horizon_principal"]
    e = ic[f"{nom}:h{hp}"]["ecart"]
    autres = [ic[f"{nom}:h{h}"]["ecart"] for h in essai["horizons_seances"] if h != hp]
    motifs = []
    if not e.get("available"):
        motifs.append("écart d'IC non mesuré (UNCALIBRATED)")
    else:
        if not (e["ecart_ic_moyen"] > 0 and e["p_signes"] < 0.05):
            motifs.append(f"écart d'IC {e['ecart_ic_moyen']:+.4f}, p {e['p_signes']:.3f}")
        if not (e["ecart_premiere_moitie"] > 0 and e["ecart_seconde_moitie"] > 0):
            motifs.append("écart d'IC de signe différent entre les deux moitiés")
        if not all(a.get("available") and a["ecart_ic_moyen"] > 0 for a in autres):
            motifs.append("écart d'IC non positif à l'autre horizon")
    facteur = not motifs
    if not strategie.get("promoted"):
        motifs += strategie.get("reasons") or ["gate non mesuré"]
    if not sabotage.get("survives"):
        motifs.append("sabotage non survécu ou non mesuré")
    if not (face_temoin.get("available") and face_temoin["ic95"][0] > 0):
        motifs.append("portefeuille : l'intervalle face au témoin n'exclut pas 0")
    promouvable = facteur and bool(strategie.get("promoted")) and bool(
        sabotage.get("survives")) and bool(
        face_temoin.get("available") and face_temoin["ic95"][0] > 0)
    return {"facteur_retenu": facteur, "strategie_promouvable": promouvable,
            "motifs": motifs}


def mesurer(pan: dict[str, Any], essai: dict[str, Any], couts: np.ndarray | float,
            chemin_ledger: str | Path | None = None, n_nulles: int = 2000) -> dict[str, Any]:
    """L'essai complet sur un panneau. Rien n'est écrit : l'appelant consigne."""
    from packages.research.adversarial import sabotage_verdict
    ic = mesurer_ic(pan, essai, n_nulles)
    principal = _candidat(essai["variante_principale"])
    cand = rendements(pan, principal, essai, couts)
    # Le témoin choisit ses 12 lignes parmi les titres que le candidat sait classer.
    tem = rendements(pan, sur_coupe_commune(_temoin(essai), principal), essai, couts)
    if not (cand["available"] and tem["available"]):
        return {"available": False, "status": "UNCALIBRATED", "ic": ic}
    pl = placebo(pan, principal, essai, couts,
                 _sharpe(cand["actif"]))
    pbo = pbo_variantes(pan, essai, couts)
    strategie = gate(cand["actif"], pbo.get("pbo"), pl["p"], chemin_ledger)
    sabotage = sabotage_verdict(cand["actif"], turnover=cand["rotation_par_jour"])
    face = contre_temoin(cand, tem, essai)
    return {"available": True, "ic": ic, "placebo": pl, "pbo": pbo, "gate": strategie,
            "sabotage": sabotage, "face_temoin": face,
            "episodes": statistiques_episodes(cand["episodes"]),
            "compteurs": cand["compteurs"], "n_jours": int(cand["actif"].size),
            "decision": decision(ic, essai, strategie, sabotage, face)}
