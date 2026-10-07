"""Diagnostic du satellite actions : POURQUOI il est vide, dit à l'écran.

Extrait de `scripts/run_live.py` (audit du 06/10). Affichage seul, aucune décision.
"""

from __future__ import annotations

from packages.common.journal_passage import dire


def diag_preset(snap: dict, targets: list) -> None:
    """Dit POURQUOI le satellite actions est vide, au lieu de le laisser deviner.

    Le 26/08, un compte paper sans AUCUNE action a résisté à trois hypothèses
    successives (plancher, horaires de marché, mode léger) simplement parce que
    rien ne disait où la chaîne s'arrêtait. Affiché seulement en cas de problème."""
    # CHEMIN EXACT. `preset_diagnostic` est publié sous `dashboard`, pas à la racine :
    # le lire à la racine renvoyait toujours {} et affichait « aucun diagnostic publié »
    # alors qu'il existait. Repli sur la racine au cas où le schéma évoluerait.
    d = ((snap.get("dashboard") or {}).get("preset_diagnostic")
         or snap.get("preset_diagnostic") or {})
    # NE PAS compter les cibles par classe d'actifs : le CŒUR indiciel (QQQ) est
    # une action, donc un satellite vide passait pour rempli et le diagnostic se
    # taisait — le défaut qu'il devait justement révéler. Le signal direct est
    # l'étage « poids retenus », inscrit seulement si au moins une ligne sort.
    _ = targets          # conservé pour la signature ; le signal vient du diagnostic
    a_des_poids = any(e.get("etape") == "poids retenus"
                      for e in (d.get("etapes") or []))
    if a_des_poids and not d.get("bloque"):
        return
    dire("\n  DIAGNOSTIC DU SATELLITE ACTIONS")
    for e in d.get("etapes") or []:
        dire(f"    {e.get('etape', ''):<22} {e.get('detail', '')}")
    portes = d.get("portes") or {}
    if portes:
        tot = 1.0
        for v in portes.values():
            tot *= v
        detail = " × ".join(f"{k} {v:.3f}" for k, v in portes.items())
        dire(f"    {'exposition brute':<22} {detail}  =  {tot:.4f}")
    if d.get("arret"):
        dire(f"    ⛔ ARRÊT : {d['arret']}")
    elif not d.get("etapes"):
        dire("    (aucun diagnostic publié — snapshot antérieur à l'ADR-0044 ?)")
    elif not a_des_poids:
        dire("    (aucun poids produit, sans étage bloquant signalé — anomalie)")
