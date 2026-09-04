"""Un scan est un ESSAI : il se compte, ou le Sharpe déflaté ment.

CE QUE CE MODULE EMPÊCHE. Un scanner piloté en langage naturel balaie 200 titres en une
minute. C'est sa qualité, et c'est exactement ce qui en fait une machine à tests
multiples : « RSI < 30 et volume +200 % », puis « et si c'était 25 ? », puis « et sur du
4 h ? ». Chaque variante est un essai. Vingt essais non enregistrés font passer pour
significatif ce qui ne l'est pas — c'est le p-hacking dans sa forme la plus confortable,
parce que rien ne le signale et que chaque question paraît légitime.

Le dépôt possède déjà le remède : `ledger` compte les essais, `deflation_params` en tire
le `N` du Deflated Sharpe Ratio. Il manquait le câble entre le scanner et lui.

LE RETOURNEMENT, ET C'EST LA RAISON D'ÊTRE DU MODULE. Aujourd'hui le compte d'essais est
SOUS-ESTIMÉ : les idées essayées à la main ne sont journalisées nulle part, donc `N` ne
voit qu'une fraction de la recherche réelle et le DSR déflate trop peu. Un scanner qui
enregistre rend ce compte honnête pour la première fois. La fonctionnalité qui menaçait
la statistique devient ce qui la répare.

IDEMPOTENCE, ET POURQUOI ELLE EST OBLIGATOIRE ICI. Rejouer le même scan n'est pas un
nouvel essai : c'est la même question posée deux fois. La compter deux fois gonflerait
`N` et sur-déflaterait — l'erreur symétrique de celle qu'on corrige, et tout aussi
fausse. L'empreinte des critères sert donc de clé : mêmes critères, même essai.

CE QUE CE MODULE NE FAIT PAS. Il n'interprète aucune phrase. Traduire « RSI sous 30 » en
critères est le travail du modèle qui appelle ; valider, exécuter et COMPTER est le
travail d'ici. Un parseur de langage naturel enfoui dans la couche de recherche serait
intestable et silencieusement faux.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

# Opérateurs admis. Liste FERMÉE : un scan doit être rejouable et vérifiable, ce
# qu'aucune expression arbitraire ne garantit.
OPERATEURS = frozenset({"<", "<=", ">", ">=", "==", "!="})

FACTEUR = "scan_ad_hoc"          # famille d'essais sous laquelle les scans se comptent


class CritereInvalide(ValueError):
    """Critère rejeté AVANT exécution — jamais silencieusement ignoré.

    Ignorer un critère mal formé exécuterait un scan différent de celui demandé et
    l'enregistrerait sous l'empreinte du scan demandé : deux mensonges d'un coup."""


def valider(criteres: list[dict]) -> list[dict]:
    """Vérifie la forme de chaque critère et renvoie la liste NORMALISÉE (triée).

    Le tri rend l'empreinte indépendante de l'ordre de saisie : « RSI puis volume » et
    « volume puis RSI » sont le même scan, donc le même essai."""
    if not criteres:
        raise CritereInvalide("aucun critère : un scan sans filtre n'est pas un essai")
    out = []
    for c in criteres:
        champ, op = c.get("champ"), c.get("op")
        if not isinstance(champ, str) or not champ:
            raise CritereInvalide(f"champ manquant ou invalide : {c!r}")
        if op not in OPERATEURS:
            raise CritereInvalide(f"opérateur non admis : {op!r} (admis : "
                                  f"{', '.join(sorted(OPERATEURS))})")
        valeur = c.get("valeur")
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            raise CritereInvalide(f"valeur non numérique pour {champ} : {valeur!r}")
        out.append({"champ": champ, "op": op, "valeur": float(valeur)})
    return sorted(out, key=lambda c: (c["champ"], c["op"], c["valeur"]))


def empreinte(criteres: list[dict]) -> str:
    """Clé stable d'un scan : mêmes critères → même empreinte, quel que soit l'ordre."""
    brut = json.dumps(valider(criteres), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:16]


def _compare(gauche: float, op: str, droite: float) -> bool:
    if op == "<":
        return gauche < droite
    if op == "<=":
        return gauche <= droite
    if op == ">":
        return gauche > droite
    if op == ">=":
        return gauche >= droite
    if op == "==":
        return gauche == droite
    return gauche != droite


def executer(lignes: list[dict], criteres: list[dict]) -> list[dict]:
    """Applique les critères aux lignes du screener. PUR : ni réseau, ni écriture.

    Une ligne dont le champ demandé est ABSENT ou non numérique est écartée, jamais
    supposée conforme : « je ne sais pas » ne vaut pas « ça passe »."""
    valides = valider(criteres)
    out = []
    for ligne in lignes or []:
        if all(_conforme(ligne, c) for c in valides):
            out.append(ligne)
    return out


def _conforme(ligne: dict, critere: dict) -> bool:
    v = ligne.get(critere["champ"])
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v:
        return False
    return _compare(float(v), critere["op"], critere["valeur"])


def deja_enregistre(criteres: list[dict], records: list[dict]) -> bool:
    """Ce scan a-t-il déjà été compté ? Rejouer une question n'en pose pas une neuve."""
    cle = empreinte(criteres)
    return any(r.get("empreinte") == cle for r in records)


def enregistrement(criteres: list[dict], n_resultats: int, n_univers: int,
                   *, question: str | None = None) -> dict[str, Any]:
    """Essai à écrire au ledger. La THÈSE porte les critères, pas la phrase d'origine.

    On conserve la question telle qu'elle a été posée quand elle existe — elle explique
    l'intention — mais ce qui compte comme essai est le filtre RÉELLEMENT appliqué."""
    valides = valider(criteres)
    lisible = " ET ".join(f"{c['champ']} {c['op']} {c['valeur']:g}" for c in valides)
    return {
        "date": datetime.now(UTC).date().isoformat(),
        "facteur": FACTEUR, "classe": ["scan"], "horizon": "ad_hoc",
        "empreinte": empreinte(valides),
        "dsr": None, "pbo": None, "statut": "exploratoire",
        "n_resultats": int(n_resultats), "n_univers": int(n_univers),
        "these": f"Scan : {lisible} → {n_resultats}/{n_univers} titres."
                 + (f" Question : « {question} »." if question else ""),
    }
