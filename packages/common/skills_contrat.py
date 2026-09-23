"""Un contrat de Skill est-il complet, et décrit-il un composant qui EXISTE ?

POURQUOI CE MODULE. Un fichier de spécification non vérifié se dégrade en silence : un
champ oublié ne se voit qu'à la relecture, et personne ne relit un YAML écrit il y a
trois mois. Ce dépôt connaît déjà le motif — six garde-fous décidaient sans qu'un seul
compteur existe, et il a fallu une panne pour s'en apercevoir.

DEUX CONTRÔLES, ET LE SECOND EST LE PLUS UTILE :

  1. COMPLÉTUDE — les champs obligatoires du schéma sont présents et non vides. Un
     champ présent mais vide est traité comme absent : « falsification_conditions: [] »
     est une thèse infalsifiable qui se cache derrière une clé.

  2. ANCRAGE — chaque module cité dans `implementation.modules` existe réellement.
     Sans ce contrôle, un contrat peut décrire un composant imaginaire et le faire
     pendant des mois. C'est la différence entre une documentation et un contrat.

CE QU'IL NE FAIT PAS. Il ne juge pas la QUALITÉ d'une thèse ni la pertinence d'un
seuil : aucun programme ne sait faire ça. Il garantit qu'on ne peut pas OUBLIER de
se poser la question — ce qui est exactement la valeur d'une checklist.
"""

from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

# Un champ « présent mais vide » ne compte pas. Le dire ici plutôt que dans chaque test.
_VIDES = ({}, [], "", None)


def _charge(chemin: Path) -> dict:
    import yaml
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


def champs_requis(schema: dict) -> list[str]:
    return list(schema["properties"]["skill"]["required"])


def verifier(contrat: dict, requis: list[str], *,
             racine: Path | None = None) -> list[str]:
    """Liste des manquements d'UN contrat. Liste vide = conforme.

    Rend des phrases, pas des codes : un message qu'il faut aller décoder ailleurs
    finit par être ignoré."""
    s = (contrat or {}).get("skill")
    if not isinstance(s, dict):
        return ["racine `skill:` absente ou mal formée"]
    ecarts = [f"champ obligatoire absent ou vide : {k}"
              for k in requis if s.get(k) in _VIDES]
    ecarts += _ancrage(s, racine or RACINE)
    return ecarts


def _ancrage(s: dict, racine: Path) -> list[str]:
    """Les modules, tests et cibles cités existent-ils ? Un module ABSENT n'est pas une
    faute en soi — un contrat peut précéder son code — mais il doit être ASSUMÉ par un
    statut de maturité qui le dit."""
    impl = s.get("implementation") or {}
    absents = [m for m in (impl.get("modules") or []) if not (racine / m).exists()]
    if absents and s.get("maturity") not in ("experimental",):
        return [f"maturité « {s.get('maturity')} » mais module inexistant : {m}"
                for m in absents]
    return []


def rapport(dossier: Path | None = None, *, racine: Path | None = None) -> dict:
    """Balaie `skills/**/*.skill.yaml`. Rend {n, conformes, ecarts, sans_schema}."""
    r = racine or RACINE
    base = dossier or (r / "skills")
    schema_p = base / "_schema" / "skill.schema.yaml"
    if not schema_p.exists():
        return {"n": 0, "conformes": 0, "ecarts": {},
                "sans_schema": True, "motif": f"{schema_p} introuvable"}
    requis = champs_requis(_charge(schema_p))
    ecarts: dict[str, list[str]] = {}
    fichiers = sorted(base.rglob("*.skill.yaml"))
    for f in fichiers:
        manque = verifier(_charge(f), requis, racine=r)
        if manque:
            ecarts[str(f.relative_to(r))] = manque
    return {"n": len(fichiers), "conformes": len(fichiers) - len(ecarts),
            "ecarts": ecarts, "sans_schema": False}


def message(r: dict) -> str:
    if r.get("sans_schema"):
        return f"Contrats de Skills : schéma introuvable — {r.get('motif')}"
    if not r["n"]:
        return "Contrats de Skills : aucun fichier `.skill.yaml` — rien à vérifier."
    tete = f"Contrats de Skills : {r['conformes']}/{r['n']} conformes."
    if not r["ecarts"]:
        return tete
    lignes = [tete]
    for f, manques in r["ecarts"].items():
        lignes.append(f"  ✗ {f}")
        lignes += [f"      · {m}" for m in manques]
    return "\n".join(lignes)
