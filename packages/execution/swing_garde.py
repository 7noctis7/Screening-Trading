"""Garde-fous de la sleeve swing : veto du CRO, partage des symboles avec le preset.

Extraits de `swing_sleeve` (règle < 400 lignes/fichier). Aucune E/S, aucun état.
"""

from __future__ import annotations

# VETO DU CRO (décision D2 du propriétaire, 01/10/2026). La sleeve calcule un stop et
# un objectif pour chaque ordre, mais aucun des deux n'est TRANSMIS : `run_live`
# n'envoie que des ordres notionnels au marché, et `moteur_sortie.ExitEngine` est
# SHADOW. Une position ouverte par la sleeve n'avait donc AUCUN chemin de sortie, et sa
# protection multi-jour la soustrayait aussi au preset : elle restait indéfiniment.
# Le drapeau `QUANT_SWING_PAPER` ne suffit plus à l'activer. Lever le veto = brancher
# une sortie mesurée au banc (`sortie_lab`), PUIS passer cette constante à True — un
# geste visible dans le code, revu en PR, et non une variable d'environnement.
SORTIE_BRANCHEE = False


def veto_cro() -> str | None:
    """Motif du veto tant qu'aucune sortie n'est branchée ; None une fois levé."""
    if SORTIE_BRANCHEE:
        return None
    return ("aucune sortie branchée : stop et objectif calculés mais jamais transmis "
            "(ExitEngine SHADOW) — veto CRO D2 du 01/10")


def retirer_chevauchements(swing_orders: list[dict], targets: list[dict],
                           normalize=str) -> tuple[list[dict], list[str]]:
    """Retire de la sleeve tout symbole déjà ciblé par le preset (B2, audit du 01/10).

    Les deux passes de `run_live` se calculent contre le MÊME détenu : un symbole
    présent des deux côtés était acheté vers la cible preset, puis vers la cible sleeve
    — deux ordres sur une seule ligne. Le preset gagne : c'est la règle mesurée.
    Renvoie (ordres gardés, symboles retirés).
    """
    cles = {normalize(o.get("broker_symbol") or o.get("symbol") or "")
            for o in targets or ()}
    garde, retires = [], []
    for o in swing_orders or ():
        sym = o.get("broker_symbol") or o.get("symbol") or ""
        (retires.append(sym) if normalize(sym) in cles else garde.append(o))
    return garde, retires
