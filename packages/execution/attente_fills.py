"""Attendre que les ordres envoyés soient LISIBLES chez le courtier, avant d'écrire.

POURQUOI CE MODULE EXISTE (22/09). `run_live` journalisait les ouvertures dans la
seconde qui suit l'envoi. Or un ordre au marché vient d'être SOUMIS : Alpaca ne le rend
dans l'historique des ordres qu'une fois CLÔTURÉ, et la position n'est pas encore
rafraîchie. La journalisation lisait donc un compte qui n'avait pas fini d'exécuter.

Mesuré ce jour-là sur le compte réel, six achats envoyés :

    TTEK   94,6140 acheté ·  0       journalisé
    PFG    47,2035 acheté ·  0       journalisé
    DUOL   20,6883 acheté ·  0       journalisé
    PSX    19,7285 acheté ·  0       journalisé
    HIMS   84,8592 acheté · 69,0000  journalisé   ← TRONQUÉ
    NEM    42,4149 acheté · 23,0000  journalisé   ← TRONQUÉ

Quatre perdus, deux tronqués : **22 695,70 $ de prix de revient absent du registre pour
une seule séance**. Les mêmes fills étaient parfaitement lisibles quarante minutes plus
tard — ce n'est donc pas une donnée manquante, c'est une lecture trop tôt.

Le prix payé n'est pas que comptable. Un achat sans prix de revient au journal est une
VENTE FUTURE sans contrepartie : c'est ainsi que CRM, acheté le 21/09 et jamais
journalisé, a été vendu le 22/09 sans produire d'aller-retour. Et comme seuls les lots
issus d'une décision journalisée portent les `features_snapshot`, chaque ouverture
perdue est aussi un point de moins pour la calibration ML — l'échantillon était
tombé à quatre lots.

CE QUE CE MODULE NE FAIT PAS. Il n'envoie rien, ne modifie aucun ordre, ne décide rien.
Il attend, et il dit ce qu'il n'a pas obtenu. L'attente est BORNÉE : au bout du délai on
journalise ce qui est lisible et on NOMME le reste, plutôt que de tenir le run ouvert.

L'horloge et la lecture sont injectées : le comportement s'éprouve sans réseau et sans
attendre réellement.
"""

from __future__ import annotations

import time
from collections.abc import Callable

# 90 s / 3 s : un ordre au marché en séance se clôture en quelques secondes ; le délai
# couvre largement le cas normal sans tenir le run ouvert quand un ordre traîne. Le pas
# est assez grand pour ne pas marteler l'API du courtier (30 lectures au pire).
DELAI_S = 90.0
PAS_S = 3.0

LU = "lu"                      # lecture réussie
ILLISIBLE = "illisible"        # le courtier n'a pas répondu — ABSENT, pas VIDE


def _lire(lire_ids: Callable[[], set[str]]) -> tuple[set[str], str]:
    """Une lecture, jamais levée. Rend (ids lus, état de la lecture).

    L'état est rendu séparément parce qu'un courtier muet et un courtier qui n'a rien
    de nouveau produisent le MÊME ensemble vide. Les confondre ferait passer une panne
    de lecture pour « les ordres ne sont pas encore prêts », et le rapport final
    accuserait l'exécution à la place du réseau.
    """
    try:
        return {str(i) for i in (lire_ids() or set()) if i}, LU
    except Exception:  # noqa: BLE001 — une attente ne casse jamais un run
        return set(), ILLISIBLE


def attendre(lire_ids: Callable[[], set[str]], attendus, *,
             delai_s: float = DELAI_S, pas_s: float = PAS_S,
             horloge: Callable[[], float] = time.monotonic,
             dormir: Callable[[float], None] = time.sleep) -> dict:
    """Attend que `attendus` soient tous lisibles, ou que `delai_s` soit écoulé.

    Rend `{"lisibles", "manquants", "tours", "attendu_s", "lectures_illisibles"}`.

    La PREMIÈRE lecture est immédiate : quand tout est déjà lisible — le cas d'un run
    tardif ou d'un marché calme — l'attente ne coûte rien. On ne dort qu'après avoir
    constaté qu'il manque quelque chose ET qu'il reste du temps.
    """
    cibles = {str(i) for i in (attendus or ()) if i}
    if not cibles:
        return {"lisibles": set(), "manquants": set(), "tours": 0,
                "attendu_s": 0.0, "lectures_illisibles": 0}
    debut, tours, illisibles = horloge(), 0, 0
    lus: set[str] = set()
    while True:
        vus, etat = _lire(lire_ids)
        tours += 1
        illisibles += 1 if etat == ILLISIBLE else 0
        lus |= vus & cibles
        reste = cibles - lus
        ecoule = horloge() - debut
        if not reste or ecoule + pas_s > delai_s:
            return {"lisibles": lus, "manquants": reste, "tours": tours,
                    "attendu_s": round(ecoule, 1), "lectures_illisibles": illisibles}
        dormir(pas_s)


def message(r: dict, noms: dict | None = None) -> str:
    """Ce que l'attente a obtenu, en une ligne — y compris quand elle a tout obtenu.

    Le silence en cas de succès serait une économie coûteuse : c'est précisément parce
    que la journalisation ne disait rien de ses lectures que quatre ouvertures ont pu
    disparaître quatre jours durant sans qu'une ligne le signale.
    """
    if not r["tours"]:
        return "Attente des fills : aucun ordre à attendre."
    base = (f"Attente des fills : {len(r['lisibles'])} ordre(s) lisible(s) "
            f"en {r['attendu_s']:.0f} s ({r['tours']} lecture(s))")
    if r["lectures_illisibles"]:
        base += f" · {r['lectures_illisibles']} lecture(s) sans réponse du courtier"
    if not r["manquants"]:
        return base + "."
    cites = sorted((noms or {}).get(i, i[:8]) for i in r["manquants"])
    return (base + f" · {len(r['manquants'])} TOUJOURS ILLISIBLE(S) après le délai : "
            + ", ".join(cites[:10])
            + ". Rattrapage : make completer-ouvertures (simulation par défaut).")
