"""Verrou d'environnement — savoir si deux runs sont comparables.

CE QUE L'AUDIT A MESURÉ. `constraints.txt` a été généré pour les seuls extras
`api`, `data` et `quant` (la régénération passe aujourd'hui par `make verrou-regen`).
Il épingle donc `numpy`, `pandas`, `scipy`… et **aucune** des bibliothèques qui
entraînent réellement un modèle : `scikit-learn`, `xgboost`, `lightgbm`,
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


# ON N'ANNONCE PLUS UN OUTIL, ON ANNONCE UNE CIBLE. Deux fois de suite, le message a
# nommé un binaire absent de la machine visée : `pip-compile` (pip-tools n'est pas une
# dépendance du projet), puis `uv` (installé sur le poste de développement, PAS sur le
# VPS). Les deux fois, l'utilisateur a lu « No such file or directory » et cherché du
# côté
# de son environnement, alors que c'était la CONSIGNE qui était fausse.
#
# Un nom d'outil est une hypothèse sur une machine qu'on ne voit pas. `make
# verrou-regen`
# n'en est pas une : la cible vit dans le Makefile que l'utilisateur vient d'exécuter
# pour
# lire ce message. Elle existe donc par construction, et c'est ELLE qui se débrouille
# avec
# l'outil — en l'installant dans le venv du projet si besoin.
COMMANDE_REGENERATION = "make verrou-regen"

# Les extras que la cible doit demander. Ils vivent ici pour qu'un test puisse vérifier
# que la recette du Makefile ne les perd pas : en oublier un rend le verrou muet sur la
# bibliothèque qui produit le modèle — le trou même que tout ceci existe pour boucher.
EXTRAS_ENTRAINEMENT = ("api", "data", "quant", "ml", "sentiment")


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
        if depouillee.startswith(("#", "@#")) or "pip install" not in depouillee:
            continue
        # INSTALLER UN OUTIL N'EST PAS INSTALLER LE PROJET. `verrou-regen` amorce `uv`
        # par un `pip install uv` sans contrainte — et c'est normal : le verrou décrit
        # les dépendances du projet, pas l'outil qui le résout. Sans cette distinction,
        # mon propre détecteur a crié « installation SANS verrou » sur la ligne
        # d'amorçage que je venais d'écrire. Un détecteur qui se déclenche sur son
        # propre correctif fait exactement le bruit qu'il devait supprimer.
        if " -e " not in depouillee and ".[" not in depouillee:
            continue
        if "-c constraints.txt" not in depouillee:
            return False, f"installation SANS verrou : {depouillee[:60]}"
    return True, "verrou appliqué à l'installation locale"


# ─── Le verrou doit venir de la machine QUI ENTRAÎNE (18/09) ───────────────────────

def _famille(os_complet: str) -> str:
    """« Linux 7.0.0-28-generic » → « Linux ». Le noyau change, pas la famille."""
    return str(os_complet or "").split()[0] if os_complet else ""


def _mineure(version: str) -> str:
    """« 3.14.4 » → « 3.14 ». Le correctif ne change rien ; la mineure, si."""
    bouts = str(version or "").split(".")
    return ".".join(bouts[:2]) if len(bouts) >= 2 else str(version or "")


def machine_de_reference(registre=None) -> dict | None:
    """L'environnement de la DERNIÈRE machine qui a réellement entraîné, ou None.

    Lu dans le registre des modèles — une trace d'entraînement, pas une constante
    écrite à la main : une constante se désynchronise en silence, une trace non.
    Aucun entraînement tracé ⇒ None, et l'appelant DOIT traiter ce cas comme « on ne
    sait pas », jamais comme « c'est la bonne machine ».
    """
    try:
        from packages.mlops.registre import Registre
        reg = registre if registre is not None else Registre()
        entrees = [e for e in reg.entrees.values() if (e.manifest or {}).get("env")]
        if not entrees:
            return None
        derniere = sorted(entrees, key=lambda e: e.version)[-1]
        env = derniere.manifest["env"]
        return {"os": env.get("os"), "machine": env.get("machine"),
                "python": env.get("python"), "version": derniere.version}
    except Exception:  # noqa: BLE001 — registre absent ou illisible : on ne sait pas
        return None


def machine_compatible(reference: dict | None,
                       courant: dict | None = None) -> tuple[bool | None, str]:
    """(verdict, motif). `None` = INDÉTERMINÉ, ce qui n'est pas « compatible ».

    MESURÉ LE 18/09. `make verrou-regen` annonce « à lancer sur la machine qui
    entraîne » — et ne vérifiait rien. Lancé sur le Mac (Darwin/arm64, Python 3.12), il
    a produit un verrou de 140 paquets qui a remplacé celui du VPS (Linux/x86_64,
    Python 3.14, 159 paquets) : plus de roues CUDA, et des épinglages résolus pour une
    autre version de Python. Le fichier était vert des deux côtés — c'est le pire cas,
    parce que rien n'invite à regarder.
    """
    if not reference:
        return None, ("aucun entraînement tracé au registre : impossible de "
                      "vérifier la machine. On ne bloque pas sur une absence.")
    ici = courant or environnement()
    ecarts = []
    if _famille(reference["os"]) != _famille(ici.get("os")):
        ecarts.append(f"OS {_famille(reference['os'])} ≠ {_famille(ici.get('os'))}")
    if reference["machine"] != ici.get("machine"):
        ecarts.append(f"architecture {reference['machine']} ≠ {ici.get('machine')}")
    if _mineure(reference["python"]) != _mineure(ici.get("python")):
        ecarts.append(f"Python {_mineure(reference['python'])} ≠ "
                      f"{_mineure(ici.get('python'))}")
    if ecarts:
        return False, " · ".join(ecarts)
    return True, (f"même machine que le dernier entraînement "
                  f"({reference['machine']}, {_famille(reference['os'])})")
