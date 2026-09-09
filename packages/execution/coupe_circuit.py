"""Branchement du disjoncteur journalier sur le run d'exécution — OBSERVATION d'abord.

CE QUE ÇA AJOUTE, ET NE DUPLIQUE PAS. `live_guards.dd_kill_switch` coupe sur le
DRAWDOWN — la perte depuis le sommet, une grandeur lente. `risk/disjoncteur` coupe
sur la perte du JOUR, une grandeur rapide. Un compte peut perdre 3 % dans la journée
sans être en drawdown notable si le sommet est loin ; l'inverse est vrai aussi. Deux
mécanismes, deux horizons, aucun ne remplace l'autre.

D'OÙ VIENT LA PERTE DU JOUR. De la COURBE D'EQUITY, pas du journal. Le journal ne
réconcilie pas avec le compte (ADR-0117 : lots fantômes, chemin d'import disparu) —
s'appuyer dessus ferait déclencher un coupe-circuit sur un chiffre faux. L'equity du
courtier, elle, est la réalité : `equity_veille − equity_du_jour`.

POURQUOI IL DÉMARRE DÉSARMÉ. Au déclenchement, le disjoncteur demande de FERMER LES
POSITIONS. C'est le geste le plus destructeur du système, et il serait décidé par un
composant qui n'a jamais tourné sur des données réelles. On l'observe donc d'abord :
il calcule, il publie, il n'agit pas. `QUANT_DISJONCTEUR=1` l'arme, une fois qu'on a
vu sur plusieurs semaines les jours où il AURAIT coupé. Armer un coupe-circuit sans
cette vérification, c'est remplacer un risque de marché par un risque d'automatisme.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

_ETAT = Path(__file__).resolve().parents[2] / ".cache" / "disjoncteur.json"
SEUIL_DEFAUT = 0.03


def arme() -> bool:
    """Le disjoncteur agit-il, ou observe-t-il ? Désarmé par défaut, exprès."""
    return os.environ.get("QUANT_DISJONCTEUR", "").strip() in {"1", "true", "oui"}


def seuil() -> float:
    try:
        return float(os.environ.get("QUANT_DISJONCTEUR_SEUIL", SEUIL_DEFAUT))
    except ValueError:
        return SEUIL_DEFAUT


def _charger():
    """Disjoncteur reconstitué depuis le disque — le verrou doit SURVIVRE au processus.

    Le cron lance un processus neuf à chaque passage : un état en mémoire seule
    remettrait le verrou à zéro à chaque fois, c'est-à-dire ne verrouillerait jamais.
    """
    from datetime import date

    from packages.risk.disjoncteur import DisjoncteurJournalier
    d = DisjoncteurJournalier(seuil=seuil())
    try:
        brut = json.loads(_ETAT.read_text())
        d.jour = date.fromisoformat(brut["jour"]) if brut.get("jour") else None
        d.perte_jour = float(brut.get("perte_jour", 0.0))
        d.verrouille = bool(brut.get("verrouille", False))
    except Exception:  # noqa: BLE001 — un état illisible se reconstruit, il ne bloque pas
        pass
    return d


def _sauver(d) -> None:
    try:
        _ETAT.parent.mkdir(parents=True, exist_ok=True)
        _ETAT.write_text(json.dumps({
            "jour": d.jour.isoformat() if d.jour else None,
            "perte_jour": round(d.perte_jour, 2), "verrouille": d.verrouille}))
    except Exception:  # noqa: BLE001
        pass


def variation_du_jour(equity: float, historique=None) -> float | None:
    """`equity − dernière equity d'un jour ANTÉRIEUR`, ou None si l'historique manque.

    Un point du JOUR MÊME est ignoré : il a pu être écrit par un passage précédent du
    même jour, et comparer l'equity à elle-même donnerait toujours zéro — un
    coupe-circuit qui ne mesure rien.
    """
    from packages.execution.equity_history import _load
    hist = historique if historique is not None else _load()
    aujourdhui = datetime.now(UTC).date().isoformat()
    passes = [h for h in hist if h.get("date") and h["date"] < aujourdhui]
    if not passes:
        return None
    veille = passes[-1]
    total = sum(float(v) for k, v in veille.items() if k != "date")
    return float(equity) - total if total > 0 else None


def evaluer(equity: float, historique=None) -> dict:
    """Observe la journée et renvoie la décision. `agit` dit si elle est APPLIQUÉE."""
    delta = variation_du_jour(equity, historique)
    if delta is None:
        return {"disponible": False, "agit": False,
                "motif": "pas d'equity antérieure : rien à comparer"}
    d = _charger()
    dec = d.observer(datetime.now(UTC), equity, pnl_realise=delta)
    _sauver(d)
    return {**dec, "disponible": True, "agit": arme() and dec["verrouille"],
            "variation_jour": round(delta, 2)}
