"""Registre UNIQUE des variables `QUANT_*` — déclarées, typées, vérifiées.

POURQUOI (audit du 06/10). 84 variables `QUANT_*` étaient lues un peu partout, chacune
avec son propre `os.environ.get`, sans aucune validation centrale. Deux pannes
silencieuses en découlaient :
  - une FAUTE DE FRAPPE (`QUANT_CADENCE_JOUR=1`) est ignorée sans un mot : le passage
    garde la valeur par défaut et l'opérateur croit avoir changé le réglage ;
  - une valeur ILLISIBLE (`QUANT_DD_TARGET=25%`) fait lever le module qui la lit, au
    milieu d'un passage, loin de la cause.

CE QUE FAIT CE MODULE. Il déclare chaque variable (type, défaut, rôle, criticité) et
`verifier()` rend la liste des anomalies de l'environnement courant : variable
inconnue (avec la plus proche connue), valeur illisible pour son type, drapeau dont la
valeur n'active rien (`QUANT_NEWS=true` alors que seul `1` active). Il NE CHANGE AUCUNE
LECTURE existante : chaque module garde son `os.environ.get` et son défaut ; un test
garantit que tout `QUANT_*` du code est déclaré ici (pas de dérive), et que le défaut
déclaré se lit avec son type.

Critique = la variable change un ordre, une taille ou une limite de risque.
"""

from __future__ import annotations

import difflib
import os
from collections.abc import Mapping
from dataclasses import dataclass

PREFIXE = "QUANT_"
_VRAI = {"1", "true", "yes", "oui", "on"}
_FAUX = {"0", "false", "no", "non", "off", ""}


@dataclass(frozen=True)
class Variable:
    nom: str
    type: str            # drapeau | bool | int | float | str | chemin | liste | choix
    defaut: str | None
    role: str
    critique: bool = False
    choix: tuple[str, ...] = ()
    secret: bool = False


from packages.common.reglages_registre import DECLAREES  # noqa: E402

_DECLAREES = tuple(Variable(*t) for t in DECLAREES)
REGISTRE: dict[str, Variable] = {v.nom: v for v in _DECLAREES}


def valide(var: Variable, brut: str) -> str | None:
    """Motif d'anomalie si `brut` ne se lit pas comme `var.type`, sinon None."""
    b = brut.strip()
    if var.type == "drapeau":
        return None if b in ("", "0", "1") else f"seul « 1 » active ({b!r} = éteint)"
    if var.type == "bool":
        return None if b.lower() in _VRAI | _FAUX else f"booléen illisible : {b!r}"
    if var.type in ("int", "float") and b:
        try:
            (int if var.type == "int" else float)(b)
        except ValueError:
            return f"{var.type} illisible : {b!r}"
    if var.type == "choix" and b.lower() not in var.choix:
        return f"{b!r} hors de {', '.join(c for c in var.choix if c) or '∅'}"
    return None


def verifier(env: Mapping[str, str] | None = None) -> list[dict]:
    """Anomalies des `QUANT_*` de l'environnement : inconnue ou illisible."""
    env = os.environ if env is None else env
    out = []
    for nom in sorted(k for k in env if k.startswith(PREFIXE)):
        var = REGISTRE.get(nom)
        if var is None:
            proche = difflib.get_close_matches(nom, REGISTRE, n=1, cutoff=0.8)
            out.append({"nom": nom, "critique": False, "motif": "inconnue — ignorée"
                        + (f" (voulez-vous dire {proche[0]} ?)" if proche else "")})
            continue
        motif = valide(var, env[nom])
        if motif:
            out.append({"nom": nom, "critique": var.critique, "motif": motif})
    return out


def effectifs(env: Mapping[str, str] | None = None, critiques_seulement=True) -> list:
    """(nom, valeur effective ou « défaut », rôle) — secrets masqués."""
    env = os.environ if env is None else env
    lignes = []
    for v in _DECLAREES:
        if critiques_seulement and not v.critique:
            continue
        brut = env.get(v.nom)
        val = ("••••" if v.secret else brut) if brut not in (None, "") else (
            f"défaut ({v.defaut})" if v.defaut is not None else "non défini")
        lignes.append((v.nom, val, v.role))
    return lignes


def annoncer(env: Mapping[str, str] | None = None, dire=print) -> list[dict]:
    """Imprime les anomalies (une ligne chacune) ; rend la liste. Ne lève jamais."""
    try:
        anomalies = verifier(env)
    except Exception as e:  # noqa: BLE001 — une vérification ne bloque pas un passage
        dire(f"  ⚠️  réglages : vérification impossible ({str(e)[:60]})")
        return []
    for a in anomalies:
        marque = "⛔" if a["critique"] else "⚠️ "
        dire(f"  {marque} réglage {a['nom']} : {a['motif']}")
    return anomalies
