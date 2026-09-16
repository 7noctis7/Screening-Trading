"""Magasin d'artefacts — une interface, plusieurs transports, une seule règle.

LA RÈGLE : RIEN N'EST ACCEPTÉ SANS VÉRIFICATION D'EMPREINTE. Un transfert qui se coupe à
99 % laisse un fichier de la bonne taille apparente et d'un contenu faux. Un modèle
tronqué se dépickle parfois, prédit n'importe quoi, et RIEN ne le signale — c'est
exactement le genre de panne qu'on découvre trois semaines plus tard en cherchant ailleurs.

POURQUOI UNE INTERFACE PLUTÔT QU'UN CHEMIN. Aujourd'hui les artefacts vivent dans
`models/` sur la machine qui entraîne. Demain ils viendront d'un GPU distant par rsync, ou
d'un seau S3. Le cœur du projet ne doit connaître aucun de ces mots : il dépose, il
récupère, il vérifie. Coupler le pipeline à un fournisseur serait le rendre otage d'une
facture.

CE MAGASIN NE SAIT PAS CE QU'IL TRANSPORTE. Il ne dépickle rien, ne charge aucun modèle,
n'exécute rien. Il déplace des octets et compare des empreintes. C'est ce qui permet de
l'appeler depuis un chemin non fiable sans y réfléchir à deux fois.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from packages.mlops.empreinte import sha256_fichier, verifier

RACINE = Path(__file__).resolve().parents[2]
MAGASIN_DEFAUT = RACINE / "artifacts"


@dataclass(frozen=True)
class Depot:
    """Résultat d'un dépôt. `empreinte` est ce qu'il faudra revérifier à l'arrivée."""

    cle: str
    empreinte: str
    octets: int


@dataclass(frozen=True)
class Recuperation:
    """Résultat d'une récupération. `conforme=False` ⇒ NE PAS UTILISER le fichier."""

    cle: str
    chemin: Path | None
    conforme: bool
    motif: str


@runtime_checkable
class MagasinArtefacts(Protocol):
    """Ce que tout transport doit savoir faire. Volontairement minuscule."""

    def deposer(self, cle: str, source: Path) -> Depot: ...
    def recuperer(self, cle: str, vers: Path, empreinte: str = "") -> Recuperation: ...
    def existe(self, cle: str) -> bool: ...
    def lister(self, prefixe: str = "") -> list[str]: ...
    def supprimer(self, cle: str) -> bool: ...


def _cle_sure(cle: str) -> str:
    """Refuse toute clé qui pourrait sortir du magasin.

    `../../etc/passwd` comme clé d'artefact écrirait hors du magasin. La clé vient d'un
    manifeste, potentiellement produit par une machine distante : elle n'est pas de
    confiance par construction.
    """
    brut = str(cle).strip()
    # L'ABSOLU EST TESTÉ AVANT LE NETTOYAGE. Dépouiller « /etc/passwd » de sa barre de tête
    # en ferait la clé relative « etc/passwd » : sûre, mais SILENCIEUSEMENT différente de ce
    # que l'appelant a demandé. Une coercition muette est exactement ce qui laisse un défaut
    # d'appel se transformer en fichier rangé au mauvais endroit, des mois durant.
    if not brut or Path(brut).is_absolute() or brut.startswith("\\"):
        raise ValueError(f"clé d'artefact refusée (absolue ou vide) : {cle!r}")
    c = brut.strip("/")
    if not c or ".." in Path(c).parts:
        raise ValueError(f"clé d'artefact refusée (remontée de chemin) : {cle!r}")
    return c


class MagasinLocal:
    """Système de fichiers. Le transport de référence : celui qu'on peut tester sans rien."""

    def __init__(self, racine: str | Path | None = None):
        self.racine = Path(racine or MAGASIN_DEFAUT)

    def _chemin(self, cle: str) -> Path:
        return self.racine / _cle_sure(cle)

    def deposer(self, cle: str, source: Path) -> Depot:
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(f"artefact introuvable : {src}")
        dest = self._chemin(cle)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Écriture puis renommage : un dépôt interrompu ne doit pas laisser un artefact
        # partiel SOUS SA CLÉ DÉFINITIVE, où il serait pris pour complet.
        tmp = dest.with_suffix(dest.suffix + ".partiel")
        shutil.copy2(src, tmp)
        tmp.replace(dest)
        return Depot(cle=_cle_sure(cle), empreinte=sha256_fichier(dest),
                     octets=dest.stat().st_size)

    def recuperer(self, cle: str, vers: Path, empreinte: str = "") -> Recuperation:
        src = self._chemin(cle)
        if not src.exists():
            return Recuperation(cle, None, False, f"absent du magasin : {cle}")
        dest = Path(vers)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".partiel")
        shutil.copy2(src, tmp)
        # VÉRIFIER AVANT DE PUBLIER. Poser le fichier à sa place définitive puis constater
        # qu'il est faux laisserait un artefact corrompu là où on va le chercher.
        if empreinte and not verifier(tmp, empreinte):
            tmp.unlink(missing_ok=True)
            return Recuperation(cle, None, False,
                                "empreinte NON conforme — transfert rejeté, rien n'est écrit")
        tmp.replace(dest)
        motif = "empreinte vérifiée" if empreinte else "aucune empreinte fournie — non vérifié"
        return Recuperation(cle, dest, True, motif)

    def existe(self, cle: str) -> bool:
        return self._chemin(cle).exists()

    def lister(self, prefixe: str = "") -> list[str]:
        if not self.racine.exists():
            return []
        out = [str(p.relative_to(self.racine)) for p in sorted(self.racine.rglob("*"))
               if p.is_file() and not p.name.endswith(".partiel")]
        return [c for c in out if c.startswith(prefixe)] if prefixe else out

    def supprimer(self, cle: str) -> bool:
        p = self._chemin(cle)
        if not p.exists():
            return False
        p.unlink()
        return True


def transferer(source: MagasinArtefacts, destination: MagasinArtefacts, cle: str,
               tampon: Path) -> Recuperation:
    """Copie un artefact d'un magasin vers un autre, empreinte vérifiée DE BOUT EN BOUT.

    C'est le chemin qu'empruntera un modèle entraîné sur GPU distant : magasin distant →
    disque local → magasin local. L'empreinte est celle calculée À LA SOURCE ; la
    recalculer en chemin ne prouverait que la fidélité du dernier saut.
    """
    if not source.existe(cle):
        return Recuperation(cle, None, False, "absent du magasin source")
    depart = source.recuperer(cle, tampon)
    if not depart.conforme or depart.chemin is None:
        return depart
    reference = sha256_fichier(depart.chemin)
    destination.deposer(cle, depart.chemin)
    arrivee = destination.recuperer(cle, tampon.with_suffix(".verif"), reference)
    tampon.with_suffix(".verif").unlink(missing_ok=True)
    if not arrivee.conforme:
        destination.supprimer(cle)
        return Recuperation(cle, None, False,
                            "altéré pendant le transfert — retiré du magasin de destination")
    return Recuperation(cle, depart.chemin, True, "transféré et vérifié de bout en bout")
