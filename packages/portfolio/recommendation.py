"""Recommandation d'univers : QUE détenir, et pas seulement comment repondérer l'existant.

Différence de nature avec `user_analysis.analyze`, qui répond « comment mieux répartir ce
que j'ai ». Ici la sélection vient du screening quotidien (filtres durs YAML puis score
composite z-score sur l'univers investable), et les poids des trois profils viennent des
mêmes moteurs de risque que l'étape 4. Aucune vue, aucun rendement attendu : « idéal »
signifie « bien réparti sur une sélection », jamais « le plus rentable ».

MISE EN GARDE PUBLIÉE AVEC LE RÉSULTAT : le pouvoir prédictif du score de sélection n'est
pas validé hors échantillon dans ce dépôt. La carte le dit ; elle ne le suppose pas.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from packages.portfolio.contraintes import (
    chemin_de_moindre_effort,
    contraindre,
    moderation_regime,
)
from packages.portfolio.conviction import scenario_conviction
from packages.portfolio.indicateurs import (
    bornes_52_semaines,
    correlation_moyenne,
    performance_realisee,
    positions_effectives,
    ratio_diversification,
)
from packages.portfolio.filtre_resultats import FENETRE_DEFAUT, ecarter
from packages.portfolio.user_analysis import (
    ALIGNEMENT,
    MIN_OBSERVATIONS,
    charger_series,
    covariance_annuelle,
    scenarios_risque,
)

# T/N minimal exigé pour une covariance empirique. En deçà, les valeurs propres sont
# dominées par l'erreur d'estimation (Marchenko-Pastur : le bruit occupe une bande de
# largeur ~(1+√(N/T))²) et un min-variance nourri de cette matrice optimise du bruit —
# il concentre sur les actifs dont la variance est SOUS-ESTIMÉE par accident.
RATIO_T_SUR_N_MIN = 30.0
MIN_ACTIFS = 3


def _debut(serie: dict[str, float]) -> str:
    return min(serie) if serie else "9999-99-99"


def _fenetre(series: dict[str, dict[str, float]]) -> int:
    if not series:
        return 0
    return len(set.intersection(*(set(valeurs) for valeurs in series.values())))


PERIME_JOURS = 10        # même seuil que le nettoyage d'univers de `build_snapshot`


def ecarter_perimes(series: dict[str, dict[str, float]],
                    seuil: int = PERIME_JOURS) -> tuple[dict, list[dict]]:
    """Retire les séries ARRÊTÉES avant tout calcul. Défense en profondeur, et elle a servi.

    Le 07/09, `BK` (dernière barre au 18 juin), `EA` (10 août) et `EQR` (21 août) occupaient
    57 % de la recommandation. Deux conséquences distinctes, la seconde plus vicieuse :

    1. L'alignement se fait par INTERSECTION des dates. Un seul actif arrêté au 18 juin
       tronque donc la fenêtre commune de TOUT le portefeuille au 18 juin — la carte
       affichait « historique commun jusqu'au 2026-06-17 » sans que personne n'y voie un
       avertissement.
    2. Une série figée n'a plus de variance récente. Un min-variance la prend pour l'actif
       le moins risqué de l'univers et la surpondère mécaniquement. La donnée morte n'est
       pas seulement inutile : elle ATTIRE le capital.

    Seuil RELATIF à la barre la plus fraîche des candidats — un seuil absolu écarterait tout
    l'univers un lundi férié ou après une semaine sans ingestion.
    """
    from datetime import date, timedelta
    fins = {symbole: max(valeurs) for symbole, valeurs in series.items() if valeurs}
    if not fins:
        return series, []
    fraiche = max(fins.values())
    try:
        limite = (date.fromisoformat(fraiche[:10]) - timedelta(days=seuil)).isoformat()
    except ValueError:                       # dates non ISO : on ne tranche pas au hasard
        return series, []
    perimes = [{"symbol": s, "last": fins[s],
                "reason": f"dernière barre {fins[s]} < {limite} — série arrêtée"}
               for s in sorted(fins) if fins[s][:10] < limite]
    retires = {ligne["symbol"] for ligne in perimes}
    return {s: v for s, v in series.items() if s not in retires}, perimes


def elaguer(series: dict[str, dict[str, float]], scores: dict[str, float],
            ratio_min: float = RATIO_T_SUR_N_MIN) -> tuple[dict, list[dict]]:
    """Retire les candidats qui rendent la covariance non estimable, et dit lesquels.

    L'intersection des calendriers est bornée par l'actif dont l'historique COMMENCE LE
    PLUS TARD : une introduction récente au milieu de quinze candidats peut réduire la
    fenêtre commune à quelques semaines. Retirer ce candidat augmente T et diminue N —
    les deux dans le bon sens. On itère jusqu'à T ≥ ratio·N, en départageant les débuts
    identiques par le score le plus faible.

    Ce qui est retiré est RENDU, avec sa date de début : un actif écarté doit être
    visible, jamais absorbé en silence.
    """
    retenus = dict(series)
    ecartes: list[dict] = []
    while len(retenus) > MIN_ACTIFS:
        t = _fenetre(retenus)
        if t >= ratio_min * len(retenus) and t > MIN_OBSERVATIONS:
            break
        tardif = max(retenus, key=lambda s: (_debut(retenus[s]), -scores.get(s, 0.0)))
        ecartes.append({"symbol": tardif, "start": _debut(retenus[tardif]),
                        "reason": "historique trop court pour la fenêtre commune"})
        del retenus[tardif]
    return retenus, ecartes


def lien_source(symbole: str) -> str:
    """Fiche de l'INSTRUMENT chez le fournisseur qui a produit nos prix.

    Pourquoi pas le site « relations investisseurs » de la société : il faudrait le déduire
    d'un nom, et un nom mal apparié enverrait vers UNE AUTRE ENTREPRISE — précisément
    l'erreur qu'on cherche à éviter. Le lien pointe donc vers la fiche du fournisseur,
    indexée par le symbole EXACT que nous avons utilisé. Si notre identifiant est faux, la
    page ouverte est fausse de la même façon, donc visiblement fausse. Un lien qui échoue
    de manière détectable vaut mieux qu'un lien plausible et faux.
    """
    return f"https://finance.yahoo.com/quote/{symbole}"


def _lignes(symboles: list[str], meta: dict[str, dict], poids: dict,
            alias: dict[str, str] | None = None,
            series: dict[str, dict[str, float]] | None = None) -> list[dict]:
    """Chaque ligne porte de quoi IDENTIFIER l'instrument, pas seulement le pondérer.

    `name` reste None quand il est absent, au lieu de retomber sur le ticker. Afficher
    « BK / BK » a l'apparence d'une information et n'en est pas une : le lecteur croit
    avoir vérifié. Un nom manquant doit se voir comme manquant, et le lien prend le relais.
    """
    return [{"symbol": s, "name": (meta.get(s, {}).get("name") or "").strip() or None,
             "sector": meta.get(s, {}).get("sector") or None,
             "asset_class": meta.get(s, {}).get("asset_class") or None,
             "venue": meta.get(s, {}).get("venue") or None,
             "currency": meta.get(s, {}).get("currency") or None,
             # Le symbole RÉELLEMENT coté : `ETH` a pu être valorisé via `ETH-USD`. C'est le
             # désambiguïsateur le plus utile — il dit quelle série a servi au calcul.
             "alias": (alias or {}).get(s) or s,
             "lien": lien_source((alias or {}).get(s) or s),
             "score": meta.get(s, {}).get("score"),
             "reason": meta.get(s, {}).get("reason", ""),
             # Bornes 52 semaines : un constat, pas un objectif de cours. La distance au
             # plus haut se lit sans contexte — −40 % exige +67 % pour revenir.
             **bornes_52_semaines((series or {}).get(s, {})),
             **{profil: round(float(vecteur[i]), 6) for profil, vecteur in poids.items()}}
            for i, s in enumerate(symboles)]


CHEMIN_IC = Path(__file__).resolve().parents[2] / "out" / "ic_screening.json"


def charger_ic(chemin: Path = CHEMIN_IC) -> dict | None:
    """Mesure d'IC produite par `make ic-screening`, ou None si jamais mesurée.

    On LIT un fichier daté au lieu de recalculer : la mesure walk-forward réexécute le
    moteur à chaque date de la grille, ce n'est pas une opération de requête HTTP.
    """
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — jamais mesuré, illisible : on le dit par None
        return None


def _avertissement(ic: dict | None) -> str:
    """L'avertissement dit l'état RÉEL de la mesure — jamais une formule figée."""
    base = ("Les poids répartissent le risque mesuré. Aucun de ces profils ne prédit un "
            "rendement, sauf « Conviction » lorsqu'il est disponible. Exploratoire — aucun ordre.")
    if not ic or not ic.get("available"):
        return ("Le pouvoir prédictif du score de sélection n'a JAMAIS été mesuré ici "
                "(`make ic-screening`). " + base)
    signe = "+" if ic.get("ic_moyen", 0) >= 0 else ""
    etat = "robuste hors échantillon" if ic.get("robuste") else "NON robuste hors échantillon"
    return (f"IC du score mesuré à {signe}{ic.get('ic_moyen', 0):.4f} sur "
            f"{ic.get('n_dates')} fenêtres disjointes de {ic.get('horizon')} jours, {etat}. " + base)


def _indisponible(raison: str, **extra) -> dict:
    return {"available": False, "reason": raison, **extra}


def recommander(screen: dict, n: int = 15, years: int = 5, plafond: float = 0.20,
                profil: dict | None = None,
                blackout_resultats: int = FENETRE_DEFAUT,
                regime: dict | None = None, ml_scores: dict | None = None,
                ml_auc: float | None = None, positions: dict | None = None,
                preferences: dict | None = None) -> dict:
    """Sélection = top `n` du screening du jour ; poids = min-var / ERC / HRP sur eux.

    `screen` est la section `/api/screen` du snapshot : elle porte déjà les filtres durs
    appliqués, la taille de l'univers investable et le score de chaque candidat. On ne
    refait pas le screening ici — on consomme son résultat, daté, tel quel.
    """
    if not screen.get("available"):
        return _indisponible("screening du jour indisponible : aucune sélection à proposer.")
    rows = list(screen.get("rows") or [])[:max(MIN_ACTIFS, int(n))]
    if len(rows) < MIN_ACTIFS:
        return _indisponible(f"screening trop maigre : {len(rows)} candidat(s), {MIN_ACTIFS} minimum.")
    meta = {r["symbol"]: r for r in rows}
    scores = {r["symbol"]: float(r.get("score") or 0.0) for r in rows}
    # Filtre d'ENTRÉE avant tout calcul : inutile d'estimer une covariance sur des titres
    # qu'on ne prendra pas. Le risque de résultats est daté et binaire — une covariance
    # historique ne le mesure pas, donc aucun optimiseur ne peut le voir.
    candidats, blackout, sans_date = ecarter(list(meta), fenetre=blackout_resultats)
    if len(candidats) < MIN_ACTIFS:
        return _indisponible(
            f"{len(blackout)} candidat(s) écarté(s) pour résultats imminents — il en reste "
            f"{len(candidats)}, {MIN_ACTIFS} minimum. Réessayer après les publications.",
            earnings_blackout=blackout)
    meta = {s: meta[s] for s in candidats}
    # La classe d'actif du screening interdit le repli crypto sur une action : sans elle,
    # `ABC` (action délistée) se ferait valoriser par `ABC-USD`, un jeton.
    series, aliases, manquants = charger_series(
        candidats, years, {s: (meta[s].get("asset_class") or "") for s in candidats})
    if len(series) < MIN_ACTIFS:
        return _indisponible("historiques insuffisants pour les candidats du jour.",
                             missing=manquants, selected=list(meta))
    series, perimes = ecarter_perimes(series)
    if len(series) < MIN_ACTIFS:
        return _indisponible(
            f"{len(perimes)} candidat(s) écarté(s) pour série arrêtée — il en reste "
            f"{len(series)}, {MIN_ACTIFS} minimum.", stale=perimes, missing=manquants)
    retenus, ecartes = elaguer(series, scores)
    symboles, covariance, dates = covariance_annuelle(retenus)
    if covariance.size == 0 or len(dates) <= MIN_OBSERVATIONS:
        return _indisponible("calendrier commun insuffisant entre les candidats retenus.",
                             missing=manquants, dropped=ecartes)
    poids = scenarios_risque(covariance)
    ic = charger_ic()
    conviction, motif_conviction = scenario_conviction(
        covariance, [scores.get(sym, 0.0) for sym in symboles], ic,
        [(ml_scores or {}).get(sym) for sym in symboles], ml_auc)
    if conviction is not None:
        poids["conviction"] = conviction
    # Le profil déclaré BORNE le résultat au lieu de le commenter. Sans profil, la contrainte
    # se réduit au plafond de ligne : le comportement d'avant, inchangé.
    # Préférences sectorielles : des CONTRAINTES personnelles, appliquées AVANT le plafond
    # de ligne et l'exposition — une exclusion est absolue, elle ne se négocie pas contre un
    # plafond. Le coût de la contrainte est mesuré et publié.
    from packages.portfolio.preferences import appliquer, cout_de_la_contrainte
    secteurs = [str(meta.get(s, {}).get("sector") or "") for s in symboles]
    prefs = {}
    for nom, vecteur in poids.items():
        resultat = appliquer(vecteur, secteurs, preferences)
        if resultat["applique"]:
            prefs[nom] = {**{k: v for k, v in resultat.items() if k != "poids"},
                          **cout_de_la_contrainte(vecteur, resultat["poids"], covariance)}
            poids[nom] = resultat["poids"]
    moderation = moderation_regime(regime, ic)
    contraintes = {nom: contraindre(vecteur, covariance, plafond, profil,
                                    moderation["facteur"])
                   for nom, vecteur in poids.items()}
    poids = {nom: c["poids"] for nom, c in contraintes.items()}
    # Ratios de STRUCTURE (ce que la matrice implique aujourd'hui) et performance RÉALISÉE
    # (ce qui s'est produit). Les deux sont des constats ; aucun n'est une prévision.
    for nom, contrainte in contraintes.items():
        vecteur = contrainte["poids"]
        contrainte |= {
            "ratio_diversification": ratio_diversification(vecteur, covariance),
            "positions_effectives": positions_effectives(vecteur),
            "correlation_moyenne": correlation_moyenne(covariance),
            **performance_realisee(retenus, symboles, vecteur),
        }
    return {
        "available": True, "symbols": symboles, "aliases": aliases,
        "rows": _lignes(symboles, meta, poids, aliases, retenus),
        "scenarios": {profil: [round(float(v), 6) for v in vecteur]
                      for profil, vecteur in poids.items()},
        "as_of": dates[-1], "start": dates[0], "n_observations": len(dates) - 1,
        "t_sur_n": round(len(dates) / max(1, len(symboles)), 1),
        "alignment": ALIGNEMENT, "annualization": 252,
        "selection": {
            "source": "screening quotidien (filtres durs YAML puis score composite z-score)",
            "asked": int(n), "kept": len(symboles),
            "universe_size": screen.get("universe_size"),
            "filters": screen.get("filters") or [],
            "missing_history": manquants, "dropped": ecartes,
            # Le blackout est publié même vide : « aucun résultat imminent » est une
            # information, et son absence d'affichage se lirait comme un filtre inactif.
            "earnings_blackout": blackout, "earnings_window": blackout_resultats,
            "earnings_unknown": sans_date,
            # Séries arrêtées : publiées avec leur dernière date. Une donnée morte n'est pas
            # seulement inutile — figée, elle paraît sans risque et attire le capital.
            "stale": perimes, "stale_window": PERIME_JOURS,
        },
        # La mesure, telle quelle. Si elle vaut UNCALIBRATED, la carte l'affiche —
        # l'absence de mesure est une information, pas un blanc à combler.
        "ic": ic or {"available": False, "status": "JAMAIS MESURÉ",
                     "reason": "Lancer `make ic-screening`."},
        "conviction_reason": motif_conviction,
        "contraintes": contraintes,
        # Chemin de moindre effort : sans les positions détenues, la question « quels
        # mouvements achètent le plus de risque évité » n'a pas de point de départ.
        "chemin": {nom: chemin_de_moindre_effort(
                       covariance, symboles, positions or {},
                       dict(zip(symboles, c["poids"])))
                   for nom, c in contraintes.items()} if positions else {},
        "profil_applique": bool(profil),
        "regime": moderation,
        "preferences": prefs,
        "plafond_ligne": plafond,
        # L'étiquette SUIT la mesure. La figer sur « non validé » alors qu'une mesure
        # existe serait aussi faux que l'inverse : on publie ce qui a été constaté.
        "caveat": _avertissement(ic),
    }
