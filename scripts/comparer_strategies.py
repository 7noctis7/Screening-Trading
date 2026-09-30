"""make comparer-strategies — SMCLXTP-A face aux stratégies du bot et au buy & hold.

Mêmes barres, même moteur, mêmes frais, mêmes KPI (`backtest/comparaison_strategies.py`).
Sources RÉELLES uniquement :
  --fmp FICHIER...          exports JSON du connecteur FMP (quotidien)
  --vps-quotidien           base locale du VPS (actions / ETF, chargeur de production)
  --vps-crypto 1h|4h|1d     crypto Binance de `data/crypto_intraday.db` (1d = 1h agrégé)
Tirage ALÉATOIRE (`--aleatoire K --graine G`) parmi les titres qui ont au moins deux ans
d'historique depuis --debut : reproductible, fixé AVANT de voir le moindre résultat.
Chaque passage consigne au registre un essai par couple (stratégie, actif).

    make comparer-strategies ARGS="--vps-quotidien --aleatoire 8 --graine 20260930"
    make comparer-strategies ARGS="--vps-crypto 4h --aleatoire 6 --graine 20260930"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAR_AN = {"1h": 8760.0, "4h": 2190.0, "1d": 365.0}


def _bars_fmp(chemins: list[str]) -> tuple[dict, dict]:
    from packages.core.models import Bar
    from scripts.smclxtp_backtest import _classe, depuis_fmp
    univers, classes = {}, {}
    for ch in chemins:
        s = depuis_fmp(ch)
        univers[s["symbole"]] = [
            Bar(s["symbole"], "1d", datetime.fromisoformat(j).replace(tzinfo=UTC),
                o, h, lo, c, float(v or 0))
            for j, o, h, lo, c, v in zip(s["jours"], s["o"], s["h"], s["l"], s["c"], s["v"],
                                         strict=True)]
        classes[s["symbole"]] = _classe(s["symbole"])
    return univers, classes


def _journalier(barres: list) -> list:
    """Barres 1h → barres quotidiennes UTC (ouverture, extrêmes, clôture du jour)."""
    from dataclasses import replace
    jours: dict = {}
    for b in barres:
        jours.setdefault(b.ts.date(), []).append(b)
    out = []
    for groupe in (jours[d] for d in sorted(jours)):
        out.append(replace(groupe[0], timeframe="1d", high=max(x.high for x in groupe),
                           low=min(x.low for x in groupe), close=groupe[-1].close,
                           volume=sum(x.volume for x in groupe)))
    return out


def _bars_vps(a: argparse.Namespace) -> tuple[dict, dict]:
    if a.vps_quotidien:
        from scripts.preset_replay import _donnees
        data, acmap, _ = _donnees()
        return data, {s: acmap.get(s, "equity") for s in data}
    from packages.research.explo_donnees import BASE_INTRADAY
    from packages.storage.bars_repo import SqliteBarsRepository
    tf_lu = "1h" if a.vps_crypto == "1d" else a.vps_crypto
    repo = SqliteBarsRepository(BASE_INTRADAY)
    try:
        syms = [r[0] for r in repo.conn.execute(
            "SELECT DISTINCT symbol FROM silver WHERE timeframe=?", (tf_lu,)).fetchall()]
        data = {s: repo.read(s, tf_lu) for s in syms}
    finally:
        repo.close()
    if a.vps_crypto == "1d":
        data = {s: _journalier(b) for s, b in data.items()}
    return data, {s: "crypto" for s in data}


def _eligibles(univers: dict, debut: str) -> list[str]:
    """Au moins deux ans de barres à partir de --debut (sinon aucun KPI n'a de sens)."""
    out = []
    for s, bars in univers.items():
        apres = [b for b in bars if b.ts.date().isoformat() >= debut]
        if apres and (apres[-1].ts - max(apres[0].ts, bars[0].ts)).days >= 730:
            out.append(s)
    return out


def _f(x, fmt: str) -> str:
    return "—" if not isinstance(x, (int, float)) or not math.isfinite(x) else fmt.format(x)


def imprimer(res: dict, syn: dict) -> None:
    print(f"\n{'stratégie':15s} {'trades':>6s} {'win':>6s} {'Sharpe méd.':>11s} "
          f"{'Sortino méd.':>12s} {'CAGR méd.':>10s} {'maxDD méd.':>10s} {'bat B&H':>8s}")
    for nom, k in syn.items():
        print(f"{nom:15s} {k['trades_total']:6d} {_f(k['win_rate_global'], '{:6.0%}')} "
              f"{_f(k['sharpe_median'], '{:11.2f}')} {_f(k['sortino_median'], '{:12.2f}')} "
              f"{_f(k['cagr_median'], '{:10.1%}')} {_f(k['maxdd_median'], '{:10.1%}')} "
              f"{k['bat_bh_sharpe'] if nom != 'buy_and_hold' else '':>5}/{len(res)}")
    print("\nSharpe par actif :")
    for sym, r in res.items():
        print(f"  {sym:10s} " + "  ".join(f"{n} {_f(r[n]['sharpe'], '{:5.2f}')}"
                                          for n in (*r.keys(),)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--fmp", nargs="+", metavar="FICHIER")
    src.add_argument("--vps-quotidien", action="store_true")
    src.add_argument("--vps-crypto", choices=("1h", "4h", "1d"))
    ap.add_argument("--debut", default="2020-01-01")
    ap.add_argument("--aleatoire", type=int, default=0, help="K actifs tirés au hasard")
    ap.add_argument("--graine", type=int, default=20260930)
    a = ap.parse_args()
    from packages.backtest.comparaison_strategies import (
        comparer,
        non_calibrees,
        synthese,
        tirage,
    )
    univers, classes = _bars_fmp(a.fmp) if a.fmp else _bars_vps(a)
    choix = _eligibles(univers, a.debut)
    if a.aleatoire:
        choix = tirage(choix, a.aleatoire, a.graine)
    print(f"Actifs ({'tirage graine ' + str(a.graine) if a.aleatoire else 'liste'}) : "
          f"{', '.join(choix)} · écartées (UNCALIBRATED) : {', '.join(non_calibrees())}")
    tf = a.vps_crypto or "1d"
    res = comparer({s: univers[s] for s in choix}, debut=a.debut, classes=classes,
                   par_an=PAR_AN[tf] if a.vps_crypto else None)
    syn = synthese(res)
    imprimer(res, syn)
    _ecrire(a, tf, choix, res, syn)
    return 0


def _ecrire(a: argparse.Namespace, tf: str, choix: list, res: dict, syn: dict) -> None:
    from packages.backtest.comparaison_strategies import STRATEGIES
    from packages.research.ledger import append_record
    source = "fmp" if a.fmp else ("vps-quotidien" if a.vps_quotidien else "vps-crypto")
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"comparaison_strategies:{source}:{tf}:{a.graine}",
                   "statut": "mesure", "n_essais": len(STRATEGIES) * len(choix),
                   "params": {"actifs": choix, "debut": a.debut, "aleatoire": a.aleatoire},
                   "source": "scripts/comparer_strategies.py (réel)"})
    sortie = ROOT / "out" / f"comparaison_{source}_{tf}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"actifs": choix, "synthese": syn, "detail": res,
                                  "mesure_le": datetime.now(UTC).isoformat(timespec="seconds")},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n→ {sortie.relative_to(ROOT)} · {len(STRATEGIES) * len(choix)} essais consignés.")


if __name__ == "__main__":
    raise SystemExit(main())
