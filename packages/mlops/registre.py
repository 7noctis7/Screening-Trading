"""Registre de modèles — persistant, versionné, et capable de revenir en arrière.

CE QU'IL REMPLACE. `packages.ml.governance.ModelRegistry` vit EN MÉMOIRE : il meurt avec le
processus, donc il n'a jamais rien enregistré. `packages.ml.artifact` est un cache à durée
de vie, indexé par empreinte de signature — utile au serving, mais ce n'est pas un registre :
il ne connaît ni version, ni statut, ni prédécesseur. Conséquence mesurée le 16/09 : le
modèle en production ne peut ni être daté, ni être remplacé par le précédent. **Le rollback
était impossible**, non par oubli, mais parce que rien ne gardait le précédent.

LES QUATRE STATUTS ET LEUR SENS
    candidate   entraîné et enregistré, n'a encore RIEN décidé
    production  celui que le serving charge — UN SEUL à la fois, c'est un invariant
    archived    a été en production, ne l'est plus, reste rappelable (rollback)
    rejected    écarté ; on garde la trace ET le motif, car un refus est une information

CE QUE LE REGISTRE REFUSE. Promouvoir un artefact dont l'empreinte ne correspond plus à
celle enregistrée. Un fichier modifié après coup — corruption, copie partielle, écrasement —
n'est plus le modèle qu'on a validé, et le promouvoir mettrait en production quelque chose
que personne n'a jamais mesuré.

CE REGISTRE NE PROMEUT RIEN TOUT SEUL. Il exécute une décision prise ailleurs
(`packages.ml.promotion.should_promote`, puis un humain). Il enregistre, il ordonne, il
vérifie — il ne juge pas.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from packages.mlops.empreinte import verifier
from packages.mlops.manifest import Manifest

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_DEFAUT = RACINE / "models"
FICHIER = "registre.json"

CANDIDAT = "candidate"
PRODUCTION = "production"
ARCHIVE = "archived"
REJETE = "rejected"
STATUTS = (CANDIDAT, PRODUCTION, ARCHIVE, REJETE)


@dataclass
class Entree:
    """Une version de modèle et son histoire."""

    version: str
    statut: str
    chemin: str
    manifest: dict = field(default_factory=dict)
    historique: list[dict] = field(default_factory=list)

    def noter(self, statut: str, motif: str) -> None:
        """Change le statut en GARDANT la trace du précédent. Un registre qui écrase son
        historique ne répond plus à « pourquoi ce modèle est-il en production ? »."""
        self.historique.append({
            "de": self.statut, "vers": statut, "motif": motif,
            "le": datetime.now(UTC).isoformat(),
        })
        self.statut = statut


class Registre:
    """Registre sur disque. Écriture ATOMIQUE : un plantage en plein écrit ne doit pas
    laisser un registre tronqué — ce serait perdre l'historique en voulant l'enrichir."""

    def __init__(self, dossier: str | Path | None = None):
        self.dossier = Path(dossier or os.environ.get("QUANT_MODELS_DIR")
                            or DOSSIER_DEFAUT)
        self.chemin = self.dossier / FICHIER
        self.entrees: dict[str, Entree] = {}
        self._charger()

    # ── persistance ────────────────────────────────────────────────────────────────────
    def _charger(self) -> None:
        if not self.chemin.exists():
            return
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — registre illisible : on ne l'écrase PAS
            return
        for v, d in (brut.get("entrees") or {}).items():
            self.entrees[v] = Entree(
                version=v, statut=d.get("statut", CANDIDAT), chemin=d.get("chemin", ""),
                manifest=d.get("manifest") or {}, historique=d.get("historique") or [])

    def _ecrire(self) -> None:
        self.dossier.mkdir(parents=True, exist_ok=True)
        charge = {"version_format": 1,
                  "entrees": {v: asdict(e) for v, e in self.entrees.items()}}
        fd, tmp = tempfile.mkstemp(dir=str(self.dossier), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(charge, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.chemin)      # atomique sur le même système de fichiers
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ── lecture ────────────────────────────────────────────────────────────────────────
    def production(self) -> Entree | None:
        for e in self.entrees.values():
            if e.statut == PRODUCTION:
                return e
        return None

    def par_statut(self, statut: str) -> list[Entree]:
        return sorted((e for e in self.entrees.values() if e.statut == statut),
                      key=lambda e: e.version)

    def archives(self) -> list[Entree]:
        """Anciennes productions, de la plus RÉCENTE à la plus ancienne."""
        def _quand(e: Entree) -> str:
            sortie = [h for h in e.historique if h["de"] == PRODUCTION]
            return sortie[-1]["le"] if sortie else ""
        return sorted(self.par_statut(ARCHIVE), key=_quand, reverse=True)

    # ── écriture ───────────────────────────────────────────────────────────────────────
    def enregistrer(self, manifest: Manifest, chemin_artefact: str | Path,
                    motif: str = "entraînement") -> Entree:
        """Enregistre une version comme CANDIDATE. Ne promeut rien."""
        if manifest.version in self.entrees:
            raise ValueError(f"version déjà enregistrée : {manifest.version}")
        e = Entree(version=manifest.version, statut=CANDIDAT,
                   chemin=str(chemin_artefact), manifest=manifest.en_dict())
        e.noter(CANDIDAT, motif)
        e.historique[-1]["de"] = "—"
        self.entrees[e.version] = e
        self._ecrire()
        return e

    def promouvoir(self, version: str, motif: str) -> tuple[bool, str]:
        """Met une version en production. L'ancienne passe en `archived`.

        L'empreinte est REVÉRIFIÉE ici et pas seulement à l'enregistrement : entre les deux,
        le fichier a pu être écrasé par un autre run, tronqué par un disque plein ou copié
        à moitié. Promouvoir sans revérifier mettrait en production un objet que personne
        n'a mesuré.
        """
        e = self.entrees.get(version)
        if e is None:
            return False, f"version inconnue : {version}"
        if e.statut == REJETE:
            return False, "version rejetée — la promouvoir annulerait une décision prise"
        ok, pourquoi = self._artefact_valide(e)
        if not ok:
            return False, pourquoi
        actuelle = self.production()
        if actuelle is not None and actuelle.version != version:
            actuelle.noter(ARCHIVE, f"remplacée par {version}")
        if e.statut != PRODUCTION:
            e.noter(PRODUCTION, motif)
        self._ecrire()
        return True, f"{version} en production"

    def rejeter(self, version: str, motif: str) -> tuple[bool, str]:
        """Écarte une version. Une version EN PRODUCTION ne peut pas être rejetée : il
        faudrait d'abord lui désigner une remplaçante, sinon le serving n'a plus rien."""
        e = self.entrees.get(version)
        if e is None:
            return False, f"version inconnue : {version}"
        if e.statut == PRODUCTION:
            return False, "version en production — faire un rollback d'abord"
        e.noter(REJETE, motif)
        self._ecrire()
        return True, f"{version} rejetée"

    def rollback(self, motif: str = "rollback manuel") -> tuple[bool, str]:
        """Revient à la production précédente qui existe ENCORE et dont l'empreinte tient.

        On parcourt les archives de la plus récente à la plus ancienne : un rollback qui
        échoue parce que le fichier a disparu ne doit pas s'arrêter là, il doit reculer
        encore. Le but est de RÉTABLIR un service, pas de faire un point d'histoire.
        """
        actuelle = self.production()
        for candidate in self.archives():
            ok, _ = self._artefact_valide(candidate)
            if not ok:
                continue
            if actuelle is not None:
                actuelle.noter(ARCHIVE, f"rollback vers {candidate.version} — {motif}")
            candidate.noter(PRODUCTION, motif)
            self._ecrire()
            return True, f"retour à {candidate.version}"
        return False, "aucune archive utilisable — rien vers quoi revenir"

    # ── vérification ───────────────────────────────────────────────────────────────────
    def _artefact_valide(self, e: Entree) -> tuple[bool, str]:
        p = Path(e.chemin)
        if not p.exists():
            return False, f"artefact absent : {e.chemin}"
        attendu = (e.manifest or {}).get("artefact_sha256") or ""
        if not attendu:
            # Un manifeste sans empreinte est ANTÉRIEUR au contrat. On le laisse passer —
            # refuser rendrait tout l'historique déjà écrit impromouvable — mais on le DIT.
            return True, "empreinte absente du manifeste (artefact antérieur au contrat)"
        if not verifier(p, attendu):
            return False, (f"empreinte NON conforme pour {e.version} : le fichier a changé "
                           "depuis son enregistrement")
        return True, "empreinte vérifiée"

    def orphelins(self) -> list[str]:
        """Artefacts PRÉSENTS sur disque dont aucune entrée ne parle.

        LE TROU QUE ÇA BOUCHE, ET IL ÉTAIT OUVERT. `incoherences()` n'inspectait que les
        entrées DÉJÀ inscrites : un modèle posé dans `models/` sans passer par le
        registre
        lui restait donc invisible — or c'est exactement le cas qui compte. Le 16/09,
        l'artefact à AUC 0,504 servait en production et le registre annonçait « vide » ;
        les deux affirmations étaient vraies, et rien ne les confrontait.

        Un artefact qui sert sans trace ne dit ni de quelles données ni de quel commit
        il
        vient, et `rollback` n'a rien vers quoi revenir. C'est un constat, pas une
        panne :
        il se SIGNALE, il ne bloque rien.
        """
        connus = {Path(e.chemin).name for e in self.entrees.values() if e.chemin}
        vus = sorted(p.name for p in self.dossier.glob("ml_*.pkl"))
        return [f"artefact NON TRACÉ : {n} — présent dans {self.dossier.name}/, "
                "aucune entrée ne le décrit" for n in vus if n not in connus]

    def incoherences(self) -> list[str]:
        """Ce qui ne devrait jamais arriver, et qu'on veut voir si ça arrive."""
        soucis = list(self.orphelins())
        prods = self.par_statut(PRODUCTION)
        if len(prods) > 1:
            soucis.append(f"{len(prods)} versions en production : "
                          + ", ".join(e.version for e in prods))
        for e in self.entrees.values():
            if e.statut not in STATUTS:
                soucis.append(f"{e.version} : statut inconnu « {e.statut} »")
            ok, pourquoi = self._artefact_valide(e)
            if not ok and e.statut in (PRODUCTION, ARCHIVE):
                soucis.append(f"{e.version} ({e.statut}) : {pourquoi}")
        return soucis
