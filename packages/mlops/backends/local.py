"""Calcul LOCAL — sous-processus sur le Mac ou le VPS.

CE BACKEND EST LA RÉFÉRENCE, PAS UN BOUCHON. C'est lui qui tourne tant qu'aucune charge ne
justifie un GPU loué, et c'est sur lui que le cycle de vie complet — soumission, plafond de
durée, récolte, arrêt — est éprouvé. Un `LambdaBackend` écrit plus tard devra passer les
MÊMES tests de cycle de vie ; s'il ne le peut pas, c'est l'interface qui est fausse, pas
les tests.

IL DIT CE QU'IL N'EST PAS. `impose_max_runtime()` rend `True` : un sous-processus local est
réellement tué à l'échéance, et il n'y a pas de facture qui court si la supervision meurt —
au pire un processus zombie sur une machine qu'on possède. C'est le contraire d'un GPU loué,
et c'est pourquoi le superviseur interroge cette capacité plutôt que de la supposer.

Pas de shell : `subprocess.run` reçoit une liste d'arguments. Une chaîne shell laisserait
un manifeste distant injecter une commande — et un manifeste vient potentiellement d'une
machine qu'on ne contrôle pas.
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from packages.mlops.compute import (
    ARRETE,
    ECHOUE,
    EN_COURS,
    EXPIRE,
    REUSSI,
    EtatTravail,
    Travail,
)
from packages.mlops.manifest import materiel_courant

RACINE = Path(__file__).resolve().parents[3]


class BackendLocal:
    """Exécute le travail en sous-processus, dans un répertoire de travail dédié."""

    nom = "local"

    def __init__(self, atelier: str | Path | None = None, cwd: str | Path | None = None):
        # Un répertoire par travail : deux entraînements concurrents qui écriraient leurs
        # artefacts au même endroit se voleraient mutuellement leurs fichiers.
        self.atelier = Path(atelier or (RACINE / ".cache" / "compute"))
        self.cwd = Path(cwd or RACINE)
        self._etats: dict[str, EtatTravail] = {}
        self._travaux: dict[str, Travail] = {}

    def _sortie(self, travail_id: str) -> Path:
        return self.atelier / travail_id

    def impose_max_runtime(self) -> bool:
        """Vrai : le plafond est appliqué par `subprocess` lui-même, pas par le job."""
        return True

    def cout_estime(self, runtime_s: float) -> float | None:
        """`0.0`, et c'est une VALEUR, pas une absence : une machine qu'on possède ne
        facture rien à l'heure. `None` voudrait dire « je ne sais pas », ce qui est faux."""
        _ = runtime_s
        return 0.0

    def soumettre(self, travail: Travail) -> EtatTravail:
        """Exécute SYNCHRONEMENT. Un backend distant rendra la main aussitôt ; ici, attendre
        est plus honnête que de simuler de l'asynchrone sur un `subprocess` bloquant."""
        self._travaux[travail.id] = travail
        sortie = self._sortie(travail.id)
        sortie.mkdir(parents=True, exist_ok=True)
        etat = EtatTravail(travail_id=travail.id, etat=EN_COURS,
                           debut=datetime.now(UTC).isoformat(),
                           materiel=materiel_courant())
        self._etats[travail.id] = etat
        debut = time.monotonic()
        try:
            r = subprocess.run(                              # noqa: S603 — argv, pas de shell
                travail.commande, cwd=str(self.cwd), capture_output=True, text=True,
                timeout=travail.max_runtime_s,
                env={**os.environ, **travail.env, "QUANT_SORTIE": str(sortie)})
            etat.code_sortie = r.returncode
            etat.etat = REUSSI if r.returncode == 0 else ECHOUE
            etat.message = (r.stderr or r.stdout or "")[-500:]
        except subprocess.TimeoutExpired:
            # PROTECTION 2, version locale : c'est `subprocess` qui tue, pas le job.
            etat.etat = EXPIRE
            from packages.mlops.compute import _duree
            etat.message = (f"plafond de {_duree(travail.max_runtime_s)} dépassé — "
                            "processus tué")
        except FileNotFoundError as e:
            etat.etat = ECHOUE
            etat.message = f"commande introuvable : {e}"
        except Exception as e:  # noqa: BLE001
            etat.etat = ECHOUE
            etat.message = f"{type(e).__name__}: {e}"
        etat.runtime_s = round(time.monotonic() - debut, 3)
        etat.fin = datetime.now(UTC).isoformat()
        etat.cout_usd = self.cout_estime(etat.runtime_s)
        return etat

    def etat(self, travail_id: str) -> EtatTravail:
        return self._etats.get(travail_id) or EtatTravail(
            travail_id=travail_id, etat=ECHOUE, message="travail inconnu de ce backend")

    def recuperer(self, travail_id: str, vers: Path) -> list[Path]:
        """Copie ce que le travail a écrit dans `QUANT_SORTIE` vers `vers`."""
        src = self._sortie(travail_id)
        if not src.exists():
            return []
        dest = Path(vers)
        dest.mkdir(parents=True, exist_ok=True)
        out: list[Path] = []
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            cible = dest / f.name
            cible.write_bytes(f.read_bytes())
            out.append(cible)
        return out

    def terminer(self, travail_id: str, motif: str = "") -> bool:
        """IDEMPOTENT. Le superviseur l'appelle dans un `finally` : il sera appelé sur des
        travaux déjà terminés, et cela ne doit rien casser ni rien réécrire."""
        etat = self._etats.get(travail_id)
        if etat is None:
            return False
        if not etat.termine:
            etat.etat = ARRETE
            etat.message = motif or "arrêté par le superviseur"
            etat.fin = datetime.now(UTC).isoformat()
        return True

    def nettoyer(self, travail_id: str) -> bool:
        """Efface l'atelier d'un travail. JAMAIS appelé automatiquement : un artefact
        détruit avant vérification est irrécupérable (point 7 du cahier des charges)."""
        import shutil
        src = self._sortie(travail_id)
        if not src.exists():
            return False
        shutil.rmtree(src)
        return True
