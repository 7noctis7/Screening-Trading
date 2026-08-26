"""Un ordre ENVOYÉ n'est pas un ordre EXÉCUTÉ — le chemin de prod confondait les deux.

DÉFAUT (26/08). `run_live` faisait `sent += 1` dès que l'appel courtier ne levait pas
d'exception, sans jamais regarder ce que le courtier avait RÉPONDU. Or Alpaca accepte un
ordre puis peut le rejeter : le compteur affichait « 12 ordres envoyés » là où douze
ordres
avaient été refusés. C'est ce trou, plus que le rejet lui-même, qui a laissé le
satellite
actions vide pendant des semaines sans une ligne de journal (cf. ADR-0040).

QUATRE ISSUES, pas deux. « Envoyé / échoué » est trop grossier pour un ordre au marché :

    REJETE    le courtier refuse — l'ordre ne se remplira JAMAIS. C'était l'angle mort.
    REMPLI    exécution confirmée (totale ou partielle).
    EN_COURS  accepté, remplissage pas encore confirmé. C'est le cas NORMAL au moment de
              la soumission d'un ordre au marché : exiger « rempli » ici produirait une
              fausse alerte à chaque ordre.
    INCONNU   réponse inexploitable (None, objet sans statut). Ni succès ni échec — et
              surtout pas à compter comme un succès.

La distinction REJETE / EN_COURS est tout l'intérêt du module : sans elle, on
choisit entre
ignorer les rejets (l'ancien comportement) et crier au loup à chaque ordre normal.

Duck-typé et sans dépendance : testable hors-ligne, et fonctionne quel que soit le
courtier.
"""

from __future__ import annotations

REJETE = "rejete"
REMPLI = "rempli"
EN_COURS = "en_cours"
INCONNU = "inconnu"

# Statuts de courtier → issue. Alpaca en tête ; les autres partagent ce vocabulaire.
_REJETS = frozenset({"rejected", "canceled", "cancelled", "expired", "suspended",
                     "stopped", "done_for_day", "replaced"})
_REMPLIS = frozenset({"filled", "partially_filled"})
# `submitted` et `pending` viennent du vocabulaire INTERNE
# (`packages.core.models.OrderStatus`),
# que renvoient Bitmart et Binance ; les oublier aurait classé INCONNU tous les
# ordres crypto,
# donc cessé de les compter. Vérifié contre les quatre courtiers du dépôt avant
# d'activer.
_EN_COURS = frozenset({"new", "accepted", "pending_new", "accepted_for_bidding",
                       "calculated", "held", "pending_replace", "pending_cancel",
                       "submitted", "pending"})


def _statut_brut(res) -> str:
    """Statut textuel de la réponse courtier, quel que soit son emballage."""
    if res is None:
        return ""
    if isinstance(res, bool):
        # `close_position` renvoie un BOOLÉEN, pas un ordre (cf. AlpacaBroker) :
        # True = soldé,
        # False = rien à solder ou échec. Sans ce cas, toute liquidation aurait été
        # classée
        # INCONNUE, donc cessé d'être comptée — le correctif aurait créé le défaut
        # inverse.
        return "filled" if res else "rejected"
    s = getattr(res, "status", None)
    if s is None and isinstance(res, dict):
        s = res.get("status")
    if s is None:
        return ""
    # Les enums alpaca-py s'impriment « OrderStatus.FILLED » : on garde le dernier
    # segment.
    return str(getattr(s, "value", s)).strip().lower().rsplit(".", 1)[-1]


def classer(res) -> str:
    """Issue d'une soumission. Ne lève JAMAIS — un diagnostic ne casse pas l'exécution.

    La garantie est tenue par un `try` et non par la seule prudence de `_statut_brut` :
    un objet courtier peut exposer `status` en propriété qui lève. Un test le vérifie —
    la docstring l'affirmait avant que ce soit vrai.
    """
    try:
        st = _statut_brut(res)
    except Exception:  # noqa: BLE001
        return INCONNU
    if not st:
        return INCONNU
    if st in _REJETS:
        return REJETE
    if st in _REMPLIS:
        return REMPLI
    if st in _EN_COURS:
        return EN_COURS
    return INCONNU


def motif_rejet(res) -> str:
    """Explication du courtier, si elle existe. Vide sinon — on n'invente pas de
    motif."""
    for champ in ("reject_reason", "rejected_reason", "message", "reason"):
        try:
            v = getattr(res, champ, None)
            if v is None and isinstance(res, dict):
                v = res.get(champ)
            if v:
                return str(v).replace("\n", " ")[:200]
        except Exception:  # noqa: BLE001 — un motif illisible n'est pas une panne
            continue
    return ""


def resume(res) -> str:
    """Une ligne lisible pour le journal : issue + statut brut + motif éventuel."""
    issue, st = classer(res), _statut_brut(res)
    txt = {REJETE: "❌ REJETÉ par le courtier", REMPLI: "✅ rempli",
           EN_COURS: "⏳ accepté (remplissage non confirmé)",
           INCONNU: "⚠️  issue INCONNUE — réponse courtier inexploitable"}[issue]
    if st and issue != REMPLI:
        txt += f" [{st}]"
    m = motif_rejet(res)
    return f"{txt} — {m}" if m else txt


def compte_comme_envoye(res) -> bool:
    """Un ordre rejeté ne compte PAS comme envoyé, et une issue inconnue non plus.

    Compter un rejet comme un envoi est exactement ce qui rendait le défaut invisible :
    le récapitulatif annonçait des ordres partis alors que rien n'était passé.
    """
    return classer(res) in (REMPLI, EN_COURS)
