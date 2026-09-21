"""Les compte-rendus de garde-fous, run après run — local, jamais publié.

POURQUOI UN FICHIER SÉPARÉ DU COLLECTEUR. `garde_fous` est appelé DEPUIS le chemin
d'ordre : lui donner une écriture disque, c'est créer un monde où enregistrer une
statistique fait échouer un ordre. Ici on écrit UNE fois, à la fin du run, quand plus
aucun ordre ne part.

UN POINT PAR RUN, ET C'EST UN INCRÉMENT — l'inverse exact de `frais_store`, dont chaque
point est un CUMUL depuis l'ouverture du compte et où additionner deux points
multiplierait les frais. Ici, additionner est justement la bonne opération : chaque run
rapporte ce qu'il a vu, lui seul. La distinction niveau/variation a déjà coûté un panneau
entier à ce dépôt ; elle est écrite ici pour qu'on ne la repose pas.

CE QUE CE FICHIER NE CONTIENT PAS : aucun symbole, aucune position, aucune clé. Des
compteurs, des noms de RÈGLES (`poids_ligne`, `exposition_brute`…) et des montants
agrégés. Il vit dans `.cache/` — gitignoré, local-only, même statut que
`equity_history.json` et `frais_courtier.json` — et n'entre dans aucun export statique.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "garde_fous.json"
MAX_RUNS = 2000


def _load() -> list[dict]:
    try:
        d = json.loads(_F.read_text()) if _F.exists() else []
        return d if isinstance(d, list) else []
    except Exception:  # noqa: BLE001 — un fichier illisible n'est pas un run à perdre
        return []


def record(rapport: dict, *, mode: str, horodatage: str | None = None) -> bool:
    """Ajoute le compte-rendu d'UN run. Rend `False` si l'écriture a échoué.

    Le booléen n'est pas décoratif : l'appelant DOIT le dire à l'écran. Un enregistrement
    qui échoue en silence produit un rapport qui sous-compte sans jamais l'avouer —
    c'est-à-dire le défaut même que ce dispositif existe pour rendre visible.
    """
    if not rapport:
        return True                       # rien à dire n'est pas un échec
    hist = _load()
    hist.append({"horodatage": horodatage or datetime.now(UTC).isoformat(timespec="seconds"),
                 "mode": mode,
                 "gardes": rapport})
    try:
        _F.parent.mkdir(parents=True, exist_ok=True)
        _F.write_text(json.dumps(hist[-MAX_RUNS:]))
        return True
    except Exception:  # noqa: BLE001
        return False


def charger() -> list[dict]:
    """Tous les runs connus, du plus ancien au plus récent."""
    return sorted(_load(), key=lambda r: str(r.get("horodatage") or ""))
