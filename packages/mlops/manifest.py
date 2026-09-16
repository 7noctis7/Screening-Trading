"""Manifeste d'entraînement — de quoi refaire exactement ce run, ou dire qu'on ne peut pas.

LE DÉFAUT QU'IL CORRIGE. L'artefact en production (`models/ml_*.pkl`) contient un modèle et
trois métriques. Il ne dit NI avec quelles données, NI depuis quel commit, NI avec quelles
features il a été produit. Constaté le 16/09 : `auc 0,504 · brier 0,2496 · dsr None` — et
rien ne permet de savoir ce qu'on a entraîné pour obtenir ça, donc rien ne permet de faire
mieux de façon dirigée. Un chiffre sans provenance ne se corrige pas, il se subit.

CE QUE LE MANIFESTE REFUSE DE FAIRE. Il ne remplit jamais un champ qu'il n'a pas mesuré.
Un dépôt git sale rend `git_commit` suffixé `-sale` ; une bibliothèque absente rend `None`.
Écrire une valeur plausible à la place produirait des manifestes qui ont l'air complets et
mentent — pire qu'un trou déclaré.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

# Bibliothèques dont la version change les RÉSULTATS, pas seulement la syntaxe.
BIBLIOTHEQUES = ("numpy", "pandas", "scikit-learn", "xgboost", "lightgbm", "torch", "scipy")


def git_commit(racine: Path = RACINE) -> str:
    """SHA du commit, suffixé `-sale` si l'arbre de travail est modifié.

    Le suffixe n'est pas cosmétique : un modèle entraîné depuis un arbre sale n'est pas
    reproductible à partir de ce commit, et c'est exactement ce qu'il faut savoir avant
    d'essayer de le refaire.
    """
    def _git(*a: str) -> str:
        try:
            r = subprocess.run(["git", "-C", str(racine), *a], capture_output=True,
                               text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:  # noqa: BLE001
            return ""
    sha = _git("rev-parse", "HEAD")
    if not sha:
        return "inconnu"
    return f"{sha}-sale" if _git("status", "--porcelain") else sha


def environnement() -> dict[str, str | None]:
    """Ce qui doit être identique pour espérer le même résultat."""
    env: dict[str, str | None] = {
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
    }
    for nom in BIBLIOTHEQUES:
        env[nom] = _version(nom)
    env["cuda"] = _cuda()
    return env


def _version(nom: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(nom)
    except Exception:  # noqa: BLE001 — absente = None, jamais une valeur inventée
        return None


def _cuda() -> str | None:
    try:
        import torch
        return str(torch.version.cuda) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        return None


@dataclass(frozen=True)
class Manifest:
    """Tout ce qu'il faut pour rejouer un entraînement — ou savoir que c'est impossible."""

    modele: str                       # nom logique, ex. « swing_ml »
    version: str                      # identifiant unique, ex. « swing_ml-20260916-a1b2c3 »
    run_id: str                       # identifiant d'expérience, ex. « EXP-2026-09-001 »
    git_commit: str
    dataset_hash: str
    feature_version: str
    seed: int | None
    metriques: dict = field(default_factory=dict)      # DSR / Brier / AUC OOS
    config: dict = field(default_factory=dict)         # hyperparamètres
    env: dict = field(default_factory=dict)
    prompt_version: str | None = None                  # si des features viennent d'un LLM
    artefact_sha256: str = ""
    cree_le: str = ""
    duree_s: float | None = None
    materiel: str | None = None                        # « cpu », « mps », « cuda:A100 »…
    cout_estime_usd: float | None = None

    @staticmethod
    def creer(modele: str, run_id: str, dataset_hash: str, feature_version: str,
              *, seed: int | None = None, **extra) -> Manifest:
        """Fabrique un manifeste en CAPTURANT l'environnement au moment du run."""
        sha = git_commit()
        horodatage = datetime.now(UTC)
        version = f"{modele}-{horodatage:%Y%m%d-%H%M%S}-{sha[:7]}"
        return Manifest(
            modele=modele, version=version, run_id=run_id, git_commit=sha,
            dataset_hash=dataset_hash, feature_version=feature_version, seed=seed,
            env=environnement(), cree_le=horodatage.isoformat(), **extra)

    def reproductible(self) -> tuple[bool, str]:
        """Ce run peut-il être refait à l'identique ? Sinon, POURQUOI pas."""
        manques = []
        if self.git_commit in ("", "inconnu"):
            manques.append("commit git inconnu")
        elif self.git_commit.endswith("-sale"):
            manques.append("arbre de travail modifié au moment du run")
        if not self.dataset_hash:
            manques.append("empreinte de dataset absente")
        if self.seed is None:
            manques.append("graine aléatoire non fixée")
        if not self.artefact_sha256:
            manques.append("empreinte d'artefact absente")
        return (not manques), " · ".join(manques) or "reproductible"

    def en_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def depuis_dict(d: dict) -> Manifest:
        """Tolérant aux manifestes ANCIENS : un champ ajouté plus tard ne doit pas rendre
        illisible un historique déjà écrit — sinon on perd la traçabilité en voulant
        l'améliorer."""
        connus = {f for f in Manifest.__dataclass_fields__}
        return Manifest(**{k: v for k, v in (d or {}).items() if k in connus})


def materiel_courant() -> str:
    """Étiquette du matériel réellement utilisé. `packages.common.device` fait le choix ;
    ici on se contente de le NOMMER pour le manifeste."""
    if os.environ.get("QUANT_MATERIEL"):
        return os.environ["QUANT_MATERIEL"]
    try:
        import torch
        if torch.cuda.is_available():
            return f"cuda:{torch.cuda.get_device_name(0)}"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return f"cpu:{platform.machine()}"


def _python_complet() -> str:
    return sys.version.split()[0]
