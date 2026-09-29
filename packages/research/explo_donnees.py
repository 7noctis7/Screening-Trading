"""Données et exécution du banc d'exploration : un axe de dates, des univers, une matrice R.

Tous les scénarios d'une grille sont simulés sur le MÊME axe de dates, sinon ni le
classement ni la PBO (qui découpe les lignes de R en blocs) ne compareraient la même chose.
Les univers ne sont que des sous-ensembles de lignes de la matrice de prix commune.

Données RÉELLES uniquement : quotidien via le chargeur de production (`_load_prices`),
intraday crypto via la base sidecar `data/crypto_intraday.db` (Binance 1h/4h).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE_INTRADAY = ROOT / "data" / "crypto_intraday.db"
MULTI_ACTIFS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "LQD", "HYG", "GLD",
                "SLV", "DBC", "USO", "XLRE")


def _par_an(dates: list[str]) -> float:
    """Barres par an OBSERVÉES sur l'axe (252 en actions, ~365 si crypto, 8760 en 1h)."""
    d0 = datetime.fromisoformat(dates[0][:19])
    d1 = datetime.fromisoformat(dates[-1][:19])
    annees = max((d1 - d0).total_seconds() / (365.25 * 86400), 1e-9)
    return (len(dates) - 1) / annees


def charger_quotidien() -> dict:
    """Prix quotidiens réels négociables, alignés par date (même source que la production)."""
    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    from packages.backtest.panel import aligner_par_date
    from packages.execution.routing import is_tradeable
    instr = _seed_universe()
    acmap = {m["symbol"]: m["asset_class"] for m in instr}
    devise = {m["symbol"]: m.get("currency") or "" for m in instr}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode, reels = _load_prices(instr, {m["symbol"]: _sector_of(m) for m in instr},
                                     fin - timedelta(days=_HISTORY_DAYS), fin, seed=7)
    data = {s: b for s, b in data.items()
            if s in reels and b and is_tradeable(s, acmap.get(s, "equity"))}
    noms, dates, A, diag = aligner_par_date(data, sorted(data))
    return {"noms": noms, "dates": dates, "A": A, "acmap": acmap, "devise": devise,
            "mode": mode, "diag": diag}


def charger_intraday(tf: str) -> dict:
    """Barres crypto `tf` de la base sidecar ; axe = union des horodatages (marché 24/7)."""
    from packages.storage.bars_repo import SqliteBarsRepository
    if not BASE_INTRADAY.exists():
        return {"noms": [], "dates": [], "A": np.empty((0, 0)), "acmap": {}, "devise": {},
                "mode": "absent", "diag": {"available": False}}
    repo = SqliteBarsRepository(BASE_INTRADAY)
    try:
        cur = repo.conn.execute("SELECT DISTINCT symbol FROM silver WHERE timeframe=? "
                                "ORDER BY symbol", (tf,))
        series = {s: {b.ts.astimezone(UTC).isoformat()[:19]: float(b.close)
                      for b in repo.read(s, tf) if b.close}
                  for (s,) in cur.fetchall()}
    finally:
        repo.close()
    noms = sorted(s for s, v in series.items() if v)
    dates = sorted({d for s in noms for d in series[s]})
    A = np.full((len(noms), len(dates)), np.nan)
    pos = {d: k for k, d in enumerate(dates)}
    for i, s in enumerate(noms):
        for d, v in series[s].items():
            A[i, pos[d]] = v
    return {"noms": noms, "dates": dates, "A": A, "acmap": {s: "crypto" for s in noms},
            "devise": {}, "mode": f"réel ({tf}, Binance)", "diag": {"available": bool(noms)}}


def membres(univers: str, noms: list[str], acmap: dict, devise: dict) -> list[int]:
    """Lignes de la matrice qui composent un univers nommé de la grille."""
    classe = lambda s: acmap.get(s, "equity")                          # noqa: E731
    regles = {
        "qqq": lambda s: s == "QQQ",
        "btc": lambda s: s.split("/")[0] in ("BTC", "BTC-USD"),
        "actions_us": lambda s: classe(s) == "equity" and devise.get(s, "USD") == "USD",
        "etf": lambda s: classe(s) == "etf",
        "multi_actifs": lambda s: s in MULTI_ACTIFS or s.split("/")[0] == "BTC",
        "crypto": lambda s: classe(s) == "crypto",
    }
    if univers not in regles:
        raise ValueError(f"univers inconnu : {univers}")
    idx = [i for i, s in enumerate(noms) if regles[univers](s)]
    return idx[:1] if univers == "btc" else idx


def index_de_date(dates: list[str], borne: str) -> int:
    """Dernier indice dont la date est ≤ `borne` (−1 si aucune)."""
    k = -1
    for i, d in enumerate(dates):
        if d[:10] <= borne:
            k = i
    return k


def _regle(sc: dict) -> tuple:
    return (sc["univers"], sc["selection"], sc["ponderation"], sc["overlay"])


def executer(donnees: dict, scs: list[dict], debut: int, fin: int, par_an: float,
             bavard: bool = True) -> tuple[np.ndarray, list[dict]]:
    """R (T×N) des rendements nets de chaque scénario sur les barres debut..fin.

    Les poids d'une règle à la date t ne dépendent pas du pas : on les calcule une fois et
    on les partage entre les pas de la même règle (même résultat, beaucoup moins de calcul).
    `A` est tronquée à `fin` : aucune barre au-delà n'existe pour le moteur."""
    from packages.backtest.preset_core import couts_univers
    from packages.research.explo_moteur import simuler
    from packages.research.explo_regles import poids_a_la_date
    A = donnees["A"][:, :fin + 1]
    colonnes, gardes, cle_courante, idx, cache = [], [], None, [], {}
    for sc in scs:                   # les pas d'une même règle sont consécutifs (`scenarios`)
        if _regle(sc) != cle_courante:
            cle_courante, cache = _regle(sc), {}          # un seul cache vivant : mémoire bornée
            idx = membres(sc["univers"], donnees["noms"], donnees["acmap"], donnees["devise"])
            if bavard:
                print(f"  · {'|'.join(cle_courante)} ({len(idx)} titres)", flush=True)
        if not idx:
            continue
        sous = A[idx]
        regle = {**sc}

        def poids(t, sous=sous, regle=regle, cache=cache):
            if t not in cache:
                cache[t] = poids_a_la_date(sous, t, regle, par_an)
            return cache[t]

        couts = couts_univers([donnees["noms"][i] for i in idx], donnees["acmap"])
        r = simuler(sous, poids, sc["pas"], couts, debut, fin)
        colonnes.append(r["rendements"])
        gardes.append({**sc, "frais": round(r["frais"], 5),
                       "turnover_an": round(r["turnover"] / max(len(r["rendements"]) / par_an,
                                                                1e-9), 3)})
    R = np.column_stack(colonnes) if colonnes else np.empty((fin - debut, 0))
    return R, gardes
