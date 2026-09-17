"""Verrou d'environnement — savoir si deux runs sont comparables.

CE QUE L'AUDIT A MESURÉ. `constraints.txt` est généré par `pip-compile` pour les extras
`api`, `data` et `quant`. Il épingle donc `numpy`, `pandas`, `scipy`… et **aucune** des
bibliothèques qui entraînent réellement un modèle : `scikit-learn`, `xgboost`, `lightgbm`,
`optuna`, `mlflow`, `torch`, `transformers` sont toutes libres.

POURQUOI C'EST LE TROU LE PLUS SOURNOIS. Un modèle sérialisé avec scikit-learn 1.5 et
rechargé sous 1.7 ne lève pas toujours une erreur : il peut se charger et prédire
DIFFÉREMMENT. Une reproductibilité qu'on croit acquise et qui ne l'est pas coûte plus cher
qu'une reproductibilité absente, parce qu'on cesse de vérifier.

LE CHOIX FAIT ICI : DÉTECTER PLUTÔT QU'IMPOSER. Un fichier de verrou que personne ne
régénère devient de la cérémonie — il décrit un état qui n'existe plus, et il rassure.
Ce module compare donc l'environnement RÉELLEMENT utilisé (capturé dans le manifeste) à
celui d'aujourd'hui, et nomme les écarts. Il ne bloque rien : entraîner ailleurs — c'est
tout l'intérêt d'un GPU distant — implique par construction un environnement différent.
Ce qu'on exige n'est pas l'identité, c'est de SAVOIR.
"""

from __future__ import annotations

import re
from pathlib import Path

from packages.mlops.manifest import BIBLIOTHEQUES, environnement

RACINE = Path(__file__).resolve().parents[2]
VERROU = RACINE / "constraints.txt"

# Une différence de version MAJEURE change le comportement ; une différence de patch,
# presque jamais. On distingue, sinon tout écart se vaut et plus rien n'alerte.
GRAVE = "majeur"
MINEUR = "mineur"
ABSENT = "absent"

_EPINGLE = re.compile(r"^([A-Za-z0-9_.\-]+)==([0-9][^\s;#]*)", re.MULTILINE)


def verrou(chemin: Path = VERROU) -> dict[str, str]:
    """Versions épinglées, lues dans `constraints.txt`. Absent ⇒ dictionnaire vide."""
    if not chemin.exists():
        return {}
    texte = chemin.read_text(encoding="utf-8")
    return {n.lower().replace("_", "-"): v for n, v in _EPINGLE.findall(texte)}


def non_verrouillees(chemin: Path = VERROU) -> list[str]:
    """Bibliothèques qui changent les RÉSULTATS et que le verrou ne couvre pas.

    Calculé, jamais écrit à la main : ajouter une dépendance d'entraînement sans
    l'épingler doit se voir tout seul.
    """
    fige = verrou(chemin)
    return [b for b in BIBLIOTHEQUES if b.lower().replace("_", "-") not in fige]


def _rang(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    morceaux = re.findall(r"\d+", str(version))[:3]
    return tuple(int(x) for x in morceaux)


def comparer_versions(a: str | None, b: str | None) -> str | None:
    """`None` si compatibles, sinon la GRAVITÉ de l'écart."""
    if a == b:
        return None
    if a is None or b is None:
        return ABSENT
    ra, rb = _rang(a), _rang(b)
    if not ra or not rb:
        return MINEUR
    return GRAVE if ra[:2] != rb[:2] else MINEUR


def ecarts(env_du_run: dict, env_courant: dict | None = None) -> list[dict]:
    """Écarts entre l'environnement d'un run passé et celui d'aujourd'hui.

    L'ordre du résultat n'est pas cosmétique : le plus grave d'abord, parce qu'une liste
    de vingt lignes dont la première est un patch ne se lit pas jusqu'au bout.
    """
    courant = env_courant or environnement()
    out: list[dict] = []
    for cle in ("python", *BIBLIOTHEQUES, "cuda"):
        a, b = (env_du_run or {}).get(cle), courant.get(cle)
        if (g := comparer_versions(a, b)) is None:
            continue
        out.append({"cle": cle, "run": a, "courant": b, "gravite": g})
    return sorted(out, key=lambda e: (e["gravite"] != GRAVE, e["cle"]))


def resume(env_du_run: dict, env_courant: dict | None = None) -> str:
    """Une phrase. Vide si rien à dire — un rapport qui parle toujours n'alerte jamais."""
    es = ecarts(env_du_run, env_courant)
    if not es:
        return ""
    graves = [e for e in es if e["gravite"] == GRAVE]
    tete = f"{len(es)} écart(s) d'environnement" + (f", dont {len(graves)} MAJEUR(S)" if graves else "")
    detail = " · ".join(f"{e['cle']} {e['run'] or '—'}→{e['courant'] or '—'}" for e in es[:4])
    return f"{tete} : {detail}" + ("…" if len(es) > 4 else "")


# `uv`, PAS `pip-compile`. Ce projet s'installe avec uv (`make install`), et
# `pip-compile` appartient à `pip-tools`, absent de ses dépendances. Mesuré le 17/09 :
# `make verrou-regen` a rendu « pip-compile: No such file or directory ». Une consigne
# qui
# nomme un outil absent de la machine est pire qu'une absence de consigne — elle fait
# croire à un environnement cassé là où c'est la consigne qui l'était.
#
# uv retire les extras par DÉFAUT (d'où l'absence de `--strip-extras`, qui n'existe pas
# chez lui ; son option est `--no-strip-extras`).
COMMANDE_REGENERATION = (
    "uv pip compile --extra api --extra data --extra quant --extra ml "
    "--extra sentiment -o constraints.txt pyproject.toml")


def commande_regeneration() -> str:
    """La commande EXACTE qui produirait un verrou couvrant l'entraînement.

    Elle est rendue plutôt qu'exécutée : régénérer un verrou télécharge les dépendances et
    doit se faire sur la machine qui entraîne, pas dans un conteneur d'analyse.
    """
    return COMMANDE_REGENERATION


def applique(racine: Path = RACINE) -> tuple[bool, str]:
    """Le verrou est-il APPLIQUÉ à l'installation locale, ou seulement présent ?

    UN VERROU QU'ON N'APPLIQUE PAS EST PIRE QU'UNE ABSENCE DE VERROU : le fichier
    existe,
    `make verrou` liste des versions épinglées, et on se croit protégé. Mesuré le
    17/09 :
    `constraints.txt` n'était passé qu'aux trois workflows GitHub — jamais à `make
    install`,
    donc jamais sur la machine qui produit réellement le modèle. La CI et le VPS
    pouvaient
    diverger sans que rien ne le dise.
    """
    mk = racine / "Makefile"
    try:
        texte = mk.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False, "Makefile illisible — application du verrou invérifiable"
    for ligne in texte.splitlines():
        depouillee = ligne.strip()
        if depouillee.startswith("#") or "pip install" not in depouillee:
            continue
        if "-c constraints.txt" not in depouillee:
            return False, f"installation SANS verrou : {depouillee[:60]}"
    return True, "verrou appliqué à l'installation locale"
