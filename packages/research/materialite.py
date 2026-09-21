"""Combien de « trades » n'en sont pas ? — le poids des TRANCHES NÉGLIGEABLES.

CE QUI A ÉTÉ VU À L'ÉCRAN (19/09). Le journal reconstruit depuis les fills affiche des
lignes à **0,00 $ de P&L avec un pourcentage non nul** — « T, +3,26 %, 0 $ », « ASML,
+1,69 %, 0 $ ». Rien n'est faux : ce sont de vraies tranches FIFO, de quantité si petite
que leur gain s'arrondit à zéro. Le rejeu produit une tranche par consommation de lot,
et les reliquats d'un rééquilibrage quotidien en laissent beaucoup.

POURQUOI ÇA COMPTE QUAND MÊME. Le taux de réussite et l'espérance par trade se calculent
sur le NOMBRE de lignes. Une tranche de 0,000001 action pèse autant qu'un aller-retour
de 5 000 $ dans ces deux chiffres — donc « 49 % de réussite, +2,25 $/trade » décrit une
population dont on ignore la composition. Un dénominateur qu'on ne connaît pas rend la
statistique illisible, pas fausse : c'est pire, parce qu'elle a l'air lisible.

CE QUE CE MODULE FAIT, ET CE QU'IL NE FAIT PAS. Il MESURE : combien de lignes, quel
poids en notionnel, quelle part du réalisé. Il ne filtre rien — décider d'un seuil avant
d'avoir vu les chiffres, ce serait choisir la réponse. Le seuil
par défaut est un ordre de grandeur (1 $ de notionnel à l'entrée), pas une vérité.
"""

from __future__ import annotations

SEUIL_NOTIONNEL = 1.0      # $ engagés à l'entrée. Un ordre de grandeur, pas une vérité.


def _notionnel(t: dict) -> float:
    try:
        return abs(float(t.get("qty") or 0.0) * float(t.get("entry_price") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def poussieres(fermes: list[dict], seuil: float = SEUIL_NOTIONNEL) -> dict:
    """Les aller-retours dont l'ENJEU est négligeable, comptés et pesés.

    On mesure sur le notionnel d'ENTRÉE et non sur le P&L : un trade de 5 000 $ qui
    finit à 0,00 $ est un vrai trade qui n'a rien rapporté, et le confondre avec une
    poussière effacerait le seul cas intéressant des deux.
    """
    fermes = list(fermes or [])
    petits = [t for t in fermes if _notionnel(t) < seuil]
    realise = sum(float(t.get("pnl_net") or 0.0) for t in fermes)
    realise_petits = sum(float(t.get("pnl_net") or 0.0) for t in petits)
    return {
        "seuil_notionnel": seuil,
        "n": len(petits), "n_total": len(fermes),
        "part_des_lignes": round(len(petits) / len(fermes), 4) if fermes else 0.0,
        "realise_petits": round(realise_petits, 2),
        "part_du_realise": (round(realise_petits / realise, 4)
                            if abs(realise) > 1e-9 else None),
        # Les deux statistiques que ces lignes diluent, RECALCULÉES SANS ELLES —
        # publiées à côté des officielles, jamais à leur place : c'est une lecture, pas
        # une correction, et le lecteur doit pouvoir comparer les deux.
        **_hors_poussieres([t for t in fermes if _notionnel(t) >= seuil]),
    }


def _hors_poussieres(gros: list[dict]) -> dict:
    if not gros:
        return {"n_significatifs": 0, "win_rate_hors": None, "esperance_hors": None}
    gagnants = sum(1 for t in gros if float(t.get("pnl_net") or 0.0) > 0)
    realise = sum(float(t.get("pnl_net") or 0.0) for t in gros)
    return {"n_significatifs": len(gros),
            "win_rate_hors": round(gagnants / len(gros), 4),
            "esperance_hors": round(realise / len(gros), 2)}
