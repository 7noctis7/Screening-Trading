"""Sortie d'un passage live : l'écran pour l'opérateur, une ligne JSON pour la machine.

POURQUOI (audit du 06/10). `run_live` racontait tout par `print()` (77 appels) : lisible
à l'écran, mais rien à requêter le lendemain — « combien de passages ont reporté des
ordres hors séance ce mois-ci ? » demandait de relire des logs de cron à la main.

`dire()` imprime EXACTEMENT ce que `print()` imprimait (l'opérateur ne voit aucune
différence, les tests qui lisent la sortie non plus) et, si un journal est ouvert,
ajoute une ligne à `logs/passages/AAAA-MM-JJ.jsonl` :
    {"ts", "run", "type", "niveau", "msg", ...}
`evenement()` écrit une ligne structurée sans rien imprimer. Rien ici ne lève : un
disque plein ne doit pas interrompre un passage d'ordres. Sous pytest, aucun journal
n'est ouvert (les tests n'écrivent pas dans `logs/`).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

DOSSIER = Path("logs/passages")
_ETAT: dict = {"chemin": None, "run": None}
_ALERTES = ("⛔", "⚠", "❌", "🛑")


def ouvrir(dossier: Path | str = DOSSIER, run: str | None = None) -> Path | None:
    """Ouvre le journal du jour ; rend son chemin (None sous pytest ou en panne)."""
    if "PYTEST_CURRENT_TEST" in os.environ and dossier == DOSSIER:
        return None
    try:
        d = Path(dossier)
        d.mkdir(parents=True, exist_ok=True)
        _ETAT["chemin"] = d / f"{datetime.now(UTC).date().isoformat()}.jsonl"
        _ETAT["run"] = run or uuid.uuid4().hex[:12]
        return _ETAT["chemin"]
    except OSError:
        _ETAT["chemin"] = None
        return None


def fermer() -> None:
    _ETAT["chemin"] = _ETAT["run"] = None


def run_id() -> str | None:
    return _ETAT["run"]


def evenement(type_: str, **champs) -> None:
    """Une ligne JSON dans le journal ouvert ; rien sinon. Ne lève jamais."""
    chemin = _ETAT["chemin"]
    if chemin is None:
        return
    ligne = {"ts": datetime.now(UTC).isoformat(), "run": _ETAT["run"], "type": type_,
             **champs}
    try:
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def dire(*args, sep: str = " ", end: str = "\n", **kw) -> None:
    """`print()` à l'identique, plus une ligne `message` au journal."""
    print(*args, sep=sep, end=end, **kw)
    msg = sep.join(str(a) for a in args)
    niveau = "alerte" if any(m in msg for m in _ALERTES) else "info"
    evenement("message", niveau=niveau, msg=msg.strip())


def lire(chemin: Path | str) -> list[dict]:
    """Les lignes d'un journal (les lignes illisibles sont sautées)."""
    out = []
    try:
        for brut in Path(chemin).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(brut))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out
