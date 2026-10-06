"""Coût RÉEL de chaque ordre exécuté, décomposé — journalisation seulement.

Pour chaque ordre (achat ou vente), en points de base, avec LA convention du dépôt
(`fills.shortfall_bps`, s = +1 à l'achat, −1 à la vente) : POSITIF = un coût.

    dérive    = s · (mid_arrivée / close_décision − 1)  gap de nuit + dérive avant envoi
    shortfall = s · (prix_fill / mid_arrivée − 1)       coût d'exécution (demi-spread,
                                                        impact, délai d'exécution)
    total     = s · (prix_fill / close_décision − 1)    ce que `exec_costs` appelait
                                                        « slippage » jusqu'ici
    spread    = (ask − bid) / mid à l'arrivée           coût d'un aller-retour immédiat

`dérive + shortfall ≈ total` (à l'ordre 1). Ce n'est que la dérive qui dépend du hasard
du marché ; le shortfall est ce que l'exécution coûte. Sans cotation à l'arrivée, la
ligne est écrite avec `bench_quality = "missing"` et ses colonnes de spread et de
shortfall NULL — jamais un zéro inventé.

Table `tca_executions` dans le journal (`data/journal.db`, local, jamais commité).
Une écriture en échec ne lève jamais : la mesure ne bloque pas un passage d'ordres.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from packages.core.models import Side
from packages.execution.fills import shortfall_bps

_DDL = """
CREATE TABLE IF NOT EXISTS tca_executions (
    order_id        TEXT PRIMARY KEY,
    jour            TEXT NOT NULL,
    venue           TEXT NOT NULL,
    symbole         TEXT NOT NULL,
    cote            TEXT NOT NULL,          -- buy | sell
    qty             REAL,
    prix_fill       REAL,
    close_decision  REAL,
    bid_arrivee     REAL, ask_arrivee REAL, mid_arrivee REAL, ts_arrivee TEXT,
    bid_fill        REAL, ask_fill REAL, mid_fill REAL,
    spread_bps      REAL,
    derive_bps      REAL,
    shortfall_bps   REAL,
    total_bps       REAL,
    bench_quality   TEXT NOT NULL
);
"""
_COLS = ("order_id", "jour", "venue", "symbole", "cote", "qty", "prix_fill",
         "close_decision", "bid_arrivee", "ask_arrivee", "mid_arrivee", "ts_arrivee",
         "bid_fill", "ask_fill", "mid_fill", "spread_bps", "derive_bps",
         "shortfall_bps", "total_bps", "bench_quality")


def _bps(cote: str, prix: float | None, reference: float | None) -> float | None:
    """La convention UNIQUE du dépôt (`fills.shortfall_bps`) : positif = défavorable."""
    if prix is None:
        return None
    return shortfall_bps(reference, prix, Side.LONG if cote == "buy" else Side.SHORT)


def ligne(ordre: dict, *, prix_fill: float, qty: float, close_decision: float | None,
          arrivee: dict | None, apres: dict | None, jour: str) -> dict:
    """Une ligne TCA. `ordre` : {order_id, venue, broker_symbol, cote}."""
    c = ordre["cote"]
    arrivee, apres = arrivee or {}, apres or {}
    mid_a = arrivee.get("mid")
    return {
        "order_id": ordre["order_id"], "jour": jour, "venue": ordre["venue"],
        "symbole": ordre["broker_symbol"], "cote": ordre["cote"], "qty": qty,
        "prix_fill": prix_fill, "close_decision": close_decision,
        "bid_arrivee": arrivee.get("bid"), "ask_arrivee": arrivee.get("ask"),
        "mid_arrivee": mid_a, "ts_arrivee": arrivee.get("ts"),
        "bid_fill": apres.get("bid"), "ask_fill": apres.get("ask"),
        "mid_fill": apres.get("mid"),
        "spread_bps": arrivee.get("spread_bps"),
        "derive_bps": _bps(c, mid_a, close_decision),
        "shortfall_bps": _bps(c, prix_fill, mid_a),
        "total_bps": _bps(c, prix_fill, close_decision),
        "bench_quality": "quote" if mid_a else "missing",
    }


def enregistrer(lignes: list[dict], chemin: str | Path = "data/journal.db") -> int:
    """UPSERT par order_id (un re-run ne double rien). Rend le nombre écrit, 0 en
    panne."""
    if not lignes:
        return 0
    try:
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(chemin)) as cx:
            cx.executescript(_DDL)
            cx.executemany(
                f"INSERT OR REPLACE INTO tca_executions ({', '.join(_COLS)}) "
                f"VALUES ({', '.join('?' for _ in _COLS)})",
                [tuple(li.get(c) for c in _COLS) for li in lignes])
        return len(lignes)
    except Exception:  # noqa: BLE001 — la mesure ne bloque jamais un passage
        return 0


def lire(chemin: str | Path = "data/journal.db") -> list[dict]:
    """Toutes les lignes TCA (vide si la table n'existe pas encore). Lecture seule :
    ne crée pas de base vide."""
    if not Path(chemin).is_file():
        return []
    try:
        with sqlite3.connect(str(chemin)) as cx:
            cx.row_factory = sqlite3.Row
            return [dict(r) for r in cx.execute("SELECT * FROM tca_executions")]
    except sqlite3.Error:
        return []


def resume(lignes: list[dict], n_min: int = 20) -> dict:
    """Médianes par composante, sur les lignes qui ont une cotation d'arrivée."""
    import statistics
    ok = [li for li in lignes if li.get("bench_quality") == "quote"]
    if len(ok) < n_min:
        return {"available": False, "status": "UNCALIBRATED", "n": len(ok),
                "n_total": len(lignes)}
    out = {"available": True, "n": len(ok), "n_total": len(lignes)}
    for c in ("spread_bps", "derive_bps", "shortfall_bps", "total_bps"):
        v = [li[c] for li in ok if li.get(c) is not None]
        out[f"{c}_mediane"] = statistics.median(v) if v else None
    return out
