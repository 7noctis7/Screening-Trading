"""Source par FICHIER (JSONL) — le chemin sans clé d'API, et donc le chemin par défaut.

L'API X est payante. Faire dépendre tout l'onglet d'un abonnement rendrait la
fonctionnalité intestable et invérifiable ici. Cette source lit un fichier de lignes
JSON que n'importe quoi peut produire : un export, un script maison, un copier-coller.
Brancher plus tard l'API officielle sera UN fichier de plus dans ce dossier, sans
toucher au store, aux filtres, à la route ni à l'écran.

UNE DONNÉE LUE BAT TOUJOURS UNE DONNÉE DÉDUITE. Si la ligne porte `classification`,
`ticker`, `symbole` ou `direction`, ils sont pris tels quels. Sinon seulement,
`extraction` pré-remplit — et rend `UNKNOWN`/`None` dès qu'elle hésite.

Une ligne illisible est COMPTÉE et IGNORÉE, jamais devinée : `lire()` ne cache pas
qu'elle a laissé des lignes de côté (cf. `rejets`).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from packages.social import extraction
from packages.social.modele import Classification, Direction, Publication
from packages.social.sources import sources

DEFAUT = "data/x_posts.jsonl"


@sources.register("fichier")
class SourceFichier:
    def __init__(self, chemin: str | Path | None = None) -> None:
        self.chemin = Path(str(chemin or os.environ.get("QUANT_X_JSONL") or DEFAUT))
        self.rejets: list[str] = []

    @property
    def configuree(self) -> bool:
        return self.chemin.exists()

    def lire(self) -> list[Publication]:
        self.rejets = []
        if not self.chemin.exists():
            return []
        publications = []
        for n, ligne in enumerate(self.chemin.read_text().splitlines(), start=1):
            if not ligne.strip():
                continue
            try:
                publications.append(_depuis_json(json.loads(ligne)))
            except (ValueError, KeyError, TypeError) as e:
                self.rejets.append(f"ligne {n} : {e}")
        return publications


def _depuis_json(d: dict) -> Publication:
    texte = str(d["texte"] if "texte" in d else d["text"])
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=str(d.get("id") or d["url"]),
        compte=str(d["compte"] if "compte" in d else d["account"]).lstrip("@"),
        ts=_horodatage(d),
        texte=texte,
        classification=(Classification(d["classification"]) if d.get("classification")
                        else extraction.classification(texte)),
        ticker=str(d["ticker"]) if d.get("ticker") else tick,
        symbole=str(d["symbole"]) if d.get("symbole") else sym,
        direction=(Direction(d["direction"]) if d.get("direction")
                   else extraction.direction(texte)),
        extraits={str(k): float(v) for k, v in (d.get("extraits") or {}).items()},
        url=d.get("url"),
        images=tuple(str(u) for u in (d.get("images") or ()) if u))


def _horodatage(d: dict) -> datetime:
    brut = d.get("ts") or d.get("date") or d.get("created_at")
    if not brut:
        raise KeyError("horodatage absent : une publication sans date ne se trie pas")
    ts = datetime.fromisoformat(str(brut).replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
