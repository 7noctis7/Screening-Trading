"""Les invites, VERSIONNÉES — parce qu'un prompt fait partie du modèle.

Changer une phrase d'invite change les sorties autant qu'un changement d'hyperparamètre.
Un benchmark daté d'avant la modification ne dit plus rien du système d'après, et personne
ne s'en aperçoit : les deux produisent du JSON valide. La version d'invite est donc
enregistrée avec chaque signal et dans chaque manifeste d'entraînement qui en dépend.

RÈGLE : on n'édite JAMAIS une version publiée. On en ajoute une.
"""

from __future__ import annotations

VERSION_COURANTE = "nlp_v1"

_SYSTEME_V1 = (
    "Tu es un analyste financier. Tu classes l'impact d'une information sur UN titre.\n"
    "Tu réponds UNIQUEMENT par un objet JSON conforme au schéma fourni.\n"
    "Règles :\n"
    "- sentiment : BULLISH si l'information favorise le titre, BEARISH si elle le pénalise, "
    "NEUTRAL si l'effet est indéterminé, déjà connu du marché, ou si l'information ne "
    "concerne pas ce titre.\n"
    "- confidence_score : ta certitude, de 0.0 à 1.0. Une information ambiguë mérite une "
    "valeur basse ; n'inflate pas.\n"
    "- impact_horizon : IMMEDIATE (heures), INTRADAY (la séance), SWING (jours à semaines).\n"
    "- catalyst_summary : le fait déclencheur, en une phrase factuelle. Pas de "
    "recommandation, pas de prix cible.\n"
    "Tu ne recommandes JAMAIS d'acheter ou de vendre."
)

_INVITES: dict[str, dict[str, str]] = {
    "nlp_v1": {
        "systeme": _SYSTEME_V1,
        "utilisateur": "Titre : {ticker}\n\nInformation :\n{texte}\n\nClasse cet impact.",
    },
}


def systeme(version: str = VERSION_COURANTE) -> str:
    return _INVITES[version]["systeme"]


def utilisateur(ticker: str, texte: str, version: str = VERSION_COURANTE) -> str:
    # Le texte est borné ici et pas chez l'appelant : une dépêche de dix mille caractères
    # ferait exploser le contexte et la latence, un titre à la fois.
    return _INVITES[version]["utilisateur"].format(ticker=ticker, texte=texte[:4000])


def versions() -> list[str]:
    return sorted(_INVITES)
