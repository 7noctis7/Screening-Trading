"""Les frais RÉELS du courtier, enregistrés jour après jour.

POURQUOI CE FICHIER EXISTE (18/09). Un fill porte une quantité et un prix, jamais son
coût de transaction : chez Alpaca les frais sont des ACTIVITÉS séparées (`FEE` en
dollars, `CFEE` pour la crypto, parfois prélevée en JETONS). Un registre reconstruit
depuis les seuls ordres est donc BRUT, et l'identité du compte y perd exactement le
montant des frais — 810,30 $ mesurés ce jour-là sur 100 973,45 $.

CE QUE CE MODULE GARANTIT POUR LA SUITE. Le total est relevé à CHAQUE construction de
snapshot et conservé ici. Deux raisons, et la seconde est la vraie : l'API des activités
finit par tronquer son historique, et un coût qu'on ne sait plus lire est un coût qui
disparaît des comptes. Un fichier local, lui, garde ce qu'on a vu le jour où on l'a vu.

LE TOTAL EST UN CUMUL DEPUIS L'OUVERTURE, pas un incrément : on écrit donc un point par
jour et on lit le DERNIER, jamais une somme de points — additionner des cumuls
multiplierait les frais par le nombre de passages. C'est le même piège que la confusion
« variation » / « niveau » qui a déjà coûté un panneau entier à ce dépôt.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "frais_courtier.json"


def _load() -> list[dict]:
    try:
        return json.loads(_F.read_text()) if _F.exists() else []
    except Exception:  # noqa: BLE001
        return []


def record(frais: dict, today: str | None = None) -> None:
    """Un point par jour. Un relevé indisponible n'écrase RIEN — sans quoi une panne
    d'API d'une journée effacerait le cumul déjà connu."""
    if not (frais or {}).get("disponible"):
        return
    today = today or datetime.now(UTC).date().isoformat()
    hist = [h for h in _load() if h.get("date") != today]
    hist.append({"date": today,
                 "total_usd": round(float(frais.get("total_usd") or 0.0), 2),
                 "par_type": frais.get("par_type") or {},
                 "n_en_nature": int(frais.get("n_en_nature") or 0)})
    try:
        _F.parent.mkdir(parents=True, exist_ok=True)
        _F.write_text(json.dumps(sorted(hist, key=lambda h: h["date"])[-1500:]))
    except Exception:  # noqa: BLE001
        pass


def dernier() -> dict:
    """Le cumul le plus récent connu, ou `{"disponible": False}`.

    On rend le DERNIER point, jamais la somme : chaque point est déjà un cumul depuis
    l'ouverture du compte.
    """
    hist = _load()
    if not hist:
        return {"disponible": False,
                "motif": "aucun relevé de frais enregistré pour l'instant"}
    d = max(hist, key=lambda h: h["date"])
    return {"disponible": True, **d}
