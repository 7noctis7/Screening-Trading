"""UN SEUL rebalancement par journée — quel que soit le planificateur qui le déclenche.

CE QUE CE MODULE CORRIGE. Le 15/09, le compte paper a été rebalancé DEUX fois à trente-deux
minutes d'intervalle. Le premier passage (18:32 UTC) a ouvert treize lignes actions ; le
second (19:04 UTC) en a soldé sept à la quantité près — VEEV 7,41221008 achetées puis
vendues, TYL 6,27606728, SWKS 33,28650542, SNOW 9,16030606, PLTR 10,53971696,
OSCR 86,28256206, ASST 62,01927883 — et en a raboté trois autres. 19 886 $ ouverts,
39 712 $ brassés, −60,79 $ de perte sèche pour un portefeuille qui n'a rien gagné en échange.

POURQUOI LA FENÊTRE N'A PAS SUFFI. `scripts/fenetre_execution.py` ne déduplique RIEN par
lui-même : il ouvre un créneau de soixante minutes et compte sur le fait que le
planificateur se réveille toutes les heures — « un réveil horaire y tombe exactement une
fois », dit son propre commentaire. L'hypothèse est dans la cadence, pas dans le code. Deux
réveils dans l'heure (deux lignes de crontab, un `*/30`, une seconde machine, un
`workflow_dispatch`, un lancement à la main) et le créneau laisse passer les deux.

CE QUE CE MODULE FAIT À LA PLACE. Il ne demande pas « quelle heure est-il ? » mais
« ce compte a-t-il DÉJÀ tradé aujourd'hui ? », et il le demande AU COURTIER. C'est la seule
formulation qui résiste : un verrou sur disque ne protège que la machine qui le porte, alors
que le compte, lui, est partagé par le VPS, le Mac, GitHub Actions et la main humaine. Le
courtier est le seul endroit où les quatre se rencontrent.

LE COMPROMIS, ASSUMÉ. Un passage qui échoue à mi-chemin laisse des ordres remplis : la
reprise sera donc refusée elle aussi. C'est le sens du choix — un doublon coûte de l'argent
tout de suite (mesuré : −0,31 % sur le notionnel brassé), une journée sautée coûte un jour
de dérive. `--forcer` rend la main à l'humain, qui sait, lui, ce qui vient de se passer.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

# Un ordre minuscule ne prouve pas qu'une journée a été jouée : un résidu d'arrondi, une
# poussière de fraction. En dessous, on ne considère pas la journée comme faite.
NOTIONNEL_MINIMUM = 50.0

# Et il en faut PLUSIEURS. Un rebalancement touche une dizaine de lignes ; un ordre isolé
# est plus probablement une intervention manuelle qu'un passage complet du robot.
ORDRES_MINIMUM = 2


def jour_utc(iso: str) -> date | None:
    """Date UTC d'un horodatage de fill. Illisible → None, et l'ordre ne compte pas.

    Un horodatage qu'on ne sait pas lire ne doit jamais être compté comme « aujourd'hui » :
    il bloquerait le rebalancement du jour sur la foi d'une chaîne qu'on n'a pas comprise.
    """
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC).date()


# Nom historique, conservé : `packages.execution.passages` et les tests l'utilisent.
_jour = jour_utc


def ordres_du_jour(ordres: list[dict], jour: date) -> list[dict]:
    """Ordres REMPLIS dont le fill tombe le jour UTC donné."""
    return [o for o in (ordres or [])
            if jour_utc(str(o.get("date") or "")) == jour
            and float(o.get("qty") or 0) > 0]


def desarme() -> bool:
    """`QUANT_REBAL_MULTI=1` autorise plusieurs passages par jour — pour qui le veut
    explicitement (tests d'intégration, journée de rattrapage surveillée)."""
    return os.environ.get("QUANT_REBAL_MULTI", "") == "1"


def evaluer(ordres: list[dict], jour: date | None = None,
            notionnel_minimum: float = NOTIONNEL_MINIMUM,
            ordres_minimum: int = ORDRES_MINIMUM) -> dict:
    """Ce compte a-t-il déjà été rebalancé aujourd'hui ?

    `ordres` est l'historique des fills tel que le rend le courtier. Une liste VIDE ne
    signifie pas « pas encore tradé » : elle peut aussi vouloir dire « historique
    illisible ». Le doute profite ici au trading — refuser sur une lecture ratée
    gèlerait le robot un jour entier sans qu'on sache pourquoi.
    """
    j = jour or datetime.now(UTC).date()
    du_jour = ordres_du_jour(ordres, j)
    notionnel = sum(abs(float(o.get("notional") or 0)) for o in du_jour)
    deja = (len(du_jour) >= ordres_minimum and notionnel >= notionnel_minimum)
    return {
        "jour": j.isoformat(),
        "deja_rebalance": deja and not desarme(),
        "n_ordres": len(du_jour),
        "notionnel": round(notionnel, 2),
        "desarme": desarme(),
        "symboles": sorted({str(o.get("symbol") or "") for o in du_jour})[:12],
    }


def message(d: dict) -> str:
    """Le refus doit dire CE QUI a déjà été fait, sinon il ressemble à une panne."""
    syms = ", ".join(d["symboles"])
    # L'espace fine des milliers se pose APRÈS le formatage du nombre, jamais sur la
    # phrase entière : sinon les virgules de la liste de symboles disparaissent aussi.
    montant = f"{d['notionnel']:,.0f}".replace(",", " ")
    return (
        f"\n⛔ DÉJÀ REBALANCÉ le {d['jour']} : {d['n_ordres']} ordre(s) remplis "
        f"pour {montant} $ sur ce compte ({syms})."
        + "\n   Un second passage recalculerait une cible différente et solderait des "
          "lignes ouvertes il y a quelques minutes — c'est exactement ce qui a coûté "
          "60,79 $ le 15/09.\n"
          "   Deux planificateurs visent probablement le même compte : `crontab -l`, "
          "`systemctl list-timers`, launchd du Mac, GitHub Actions (paper.yml).\n"
          "   Forcer malgré tout : python3 scripts/run_live.py --live --yes --forcer"
    )
