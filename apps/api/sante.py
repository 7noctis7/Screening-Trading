"""« Vivante » et « capable de servir » ne sont pas la même question.

POURQUOI CE FICHIER EXISTE (21/09). `/health` rendait `{"status": "ok"}` — une CONSTANTE.
Elle ne touchait jamais au snapshot, donc le « ✓ API 200 » affiché par `make up` prouvait
une seule chose : qu'un processus acceptait une connexion TCP. Une API qui va servir des
pages dans trois minutes et une API prête rendaient exactement le même voyant vert.

CE QUE ÇA COÛTE EN VRAI. Les pages du site sont rendues côté client : le HTML arrive tout
de suite, les données attendent l'API. Si le snapshot n'est pas en cache, la première
requête le CONSTRUIT — une à trois minutes pendant lesquelles chaque page reste sur ses
squelettes. Vu de l'écran, « ça ne se charge pas ». Vu de `make up`, tout est vert. Entre
les deux, rien ne faisait le lien.

`scripts/verifier_service.sh` tenait déjà ce raisonnement POUR LE FRONT — « quelque chose
répond sur le port 3000 n'est pas le service sert le code courant ». Ce module l'étend à
l'API : on ne demande plus « ça répond ? » mais « peux-tu servir une page MAINTENANT ? ».

CE MODULE NE TOUCHE À RIEN. Pas de fastapi, pas d'I/O, pas de snapshot : deux booléens
entrent, un compte-rendu sort. C'est ce qui permet de le tester partout, et surtout ce qui
garantit qu'un contrôle de santé ne peut pas DÉCLENCHER la construction qu'il décrit —
le voyant qui allume l'incendie qu'il signale.
"""

from __future__ import annotations

PRET = "pret"
PRET_RAFRAICHISSEMENT = "pret_rafraichissement"
EN_CONSTRUCTION = "en_construction"
A_CONSTRUIRE = "a_construire"

# Chaque état dit ce que l'OPÉRATEUR va voir, pas ce que le serveur fait. « stale-while-
# revalidate » est exact et n'aide personne devant un écran qui tourne.
PHRASES: dict[str, str] = {
    PRET:
        "snapshot en cache — les pages se chargent immédiatement.",
    PRET_RAFRAICHISSEMENT:
        "snapshot en cache, rafraîchi en arrière-plan — les pages se chargent "
        "immédiatement (elles affichent la version précédente jusqu'à la fin).",
    EN_CONSTRUCTION:
        "snapshot EN COURS de construction — les pages resteront en attente "
        "jusqu'à la fin (1 à 3 min sur ce dépôt).",
    A_CONSTRUIRE:
        "AUCUN snapshot en cache — la PREMIÈRE page demandée déclenchera une "
        "construction complète (1 à 3 min) pendant laquelle les pages resteront "
        "en attente. C'est le cas après un changement du code de construction.",
}


def etat(cache_present: bool, construction: bool) -> str:
    """Les quatre situations, et une seule question pour les départager : le cache
    peut-il répondre TOUT DE SUITE ?"""
    if cache_present:
        return PRET_RAFRAICHISSEMENT if construction else PRET
    return EN_CONSTRUCTION if construction else A_CONSTRUIRE


def sante(cache_present: bool, construction: bool,
          age_s: float | None = None, ttl_s: float | None = None) -> dict:
    """Compte-rendu complet. `status` reste `ok` : des appelants le lisent déjà, et un
    contrôle de santé qui change de contrat casse les outils qui s'en servaient.

    `age_s` vaut `None` quand il n'y a pas de cache — PAS zéro. Un âge de zéro se lirait
    « tout frais » alors qu'il signifie « il n'y a rien ».
    """
    e = etat(cache_present, construction)
    return {
        "status": "ok",
        "snapshot": e,
        "sert_immediatement": bool(cache_present),
        "age_s": None if not cache_present else age_s,
        "ttl_s": ttl_s,
        "message": PHRASES[e],
    }
