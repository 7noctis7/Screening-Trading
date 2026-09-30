"""make smclxtp-backtest — performance de SMCLXTP-A (LONG → TP), titre par titre, depuis 2020.

Règles d'exécution : `packages/backtest/signal_long_tp.py`, écrites AVANT tout chiffre
(signal au close → ordre à l'ouverture suivante, une position à la fois, pas de stop,
frais du dépôt par classe : actions 5 pb, crypto 25 pb par jambe). Indicateur : version
CAUSALE de `packages/indicators/smc_lux_tp.py`, réglages du Pine (50/50, pivots manqués).
L'historique antérieur au début ne sert qu'à chauffer l'indicateur (fenêtre de 101 barres).

Sources de données RÉELLES (jamais de synthétique) :
  --fmp FICHIER...     exports JSON du connecteur FMP (eod dividend-adjusted / crypto eod)
  --yahoo TICKER...    yfinance, pour le VPS (BTC-USD, ETH-USD pour la crypto)

Méta-labelling : `ml/meta_smc.analyser` sur les LONG de tous les titres. Sous 200
événements, le filtre n'est pas entraînable : UNCALIBRATED, et c'est une mesure.

    make smclxtp-backtest ARGS="--yahoo PLTR NVDA QQQ BTC-USD ETH-USD"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "smclxtp_backtest.json"
DEBUT_DONNEES = "2019-06-01"


def _classe(symbole: str) -> str:
    s = symbole.upper()
    return "crypto" if s in {"BTCUSD", "ETHUSD"} or s.endswith("-USD") or "/" in s else "equity"


def _serie(symbole: str, lignes: list[tuple]) -> dict:
    """Lignes (jour, o, h, l, c, v) → série triée ; lignes non positives écartées."""
    lignes = sorted(x for x in lignes if all(v and v > 0 for v in x[1:5]))
    j, o, h, lo, c, v = (list(z) for z in zip(*lignes, strict=True))
    o, h, lo, c = (np.asarray(x, float) for x in (o, h, lo, c))
    incoherent = int(((h < np.maximum(o, c) - 1e-9) | (lo > np.minimum(o, c) + 1e-9)).sum())
    return {"symbole": symbole, "jours": j, "o": o, "h": h, "l": lo, "c": c, "v": v,
            "barres_incoherentes": incoherent}


def depuis_fmp(chemin: str) -> dict:
    data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    pre = "adj" if "adjClose" in data[0] else ""
    cle = (lambda k: f"adj{k.capitalize()}") if pre else (lambda k: k)     # noqa: E731
    lignes = [(r["date"][:10], r[cle("open")], r[cle("high")], r[cle("low")],
               r[cle("close")], r.get("volume") or 0.0) for r in data]
    return _serie(data[0]["symbol"], lignes)


def depuis_yahoo(ticker: str) -> dict:
    import yfinance as yf
    df = yf.download(ticker, start=DEBUT_DONNEES, auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"{ticker} : aucune donnée Yahoo")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    lignes = [(d.strftime("%Y-%m-%d"), r["Open"], r["High"], r["Low"], r["Close"],
               r["Volume"]) for d, r in df.iterrows()]
    return _serie(ticker, lignes)


def backtester(s: dict, debut: str, swing: int, pivot: int) -> dict:
    from packages.backtest.signal_long_tp import kpis, simuler
    from packages.execution.costs import CostModel
    from packages.indicators.smc_lux_tp import calculer
    classe = _classe(s["symbole"])
    ind = calculer(s["h"], s["l"], s["c"], swing_length=swing, pivot_length=pivot)
    cout = CostModel.for_asset_class(classe).round_trip_bps / 2e4
    res = simuler(s["jours"], s["o"], s["c"], ind["long_signal"], ind["take_profit_signal"],
                  debut=debut, cout=cout)
    k = kpis(res, par_an=365 if classe == "crypto" else 252)
    return {**k, "symbole": s["symbole"], "classe": classe, "cout_par_jambe": cout,
            "premier_jour_donnees": s["jours"][0],
            "barres_incoherentes": s["barres_incoherentes"],
            "trades_detail": [asdict(t) for t in res["trades"]]}


def meta(series: list[dict], swing: int, pivot: int, modele: str) -> dict:
    from packages.core.models import Bar
    from packages.ml.meta_smc import Reglages, analyser
    univers = {s["symbole"]: [Bar(s["symbole"], "1d",
                                  datetime.fromisoformat(j).replace(tzinfo=UTC),
                                  o, h, lo, c, float(v or 0))
                              for j, o, h, lo, c, v in zip(s["jours"], s["o"], s["h"], s["l"],
                                                           s["c"], s["v"], strict=True)]
               for s in series}
    return analyser(univers, Reglages(swing_length=swing, pivot_length=pivot, modele=modele))


def _f(x, fmt: str) -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else fmt.format(x)


def imprimer(res: list[dict]) -> None:
    print(f"\n{'actif':8s} {'trades':>6s} {'win':>6s} {'durée j':>8s} {'PF':>6s} {'maxDD':>8s} "
          f"{'Sharpe':>7s} {'Sortino':>8s} {'CAGR':>8s} {'PnL moy $':>10s} {'PnL moy %':>9s}"
          f"   | B&H CAGR  B&H maxDD")
    for r in res:
        b = r["buy_and_hold"]
        print(f"{r['symbole']:8s} {r['trades']:6d} {_f(r['win_rate'], '{:6.0%}')} "
              f"{_f(r['duree_moyenne_jours'], '{:8.0f}')} {_f(r['profit_factor'], '{:6.2f}')} "
              f"{_f(r['max_drawdown'], '{:8.1%}')} {_f(r['sharpe'], '{:7.2f}')} "
              f"{_f(r['sortino'], '{:8.2f}')} {_f(r['cagr'], '{:8.1%}')} "
              f"{_f(r['pnl_moyen'], '{:10,.0f}')} {_f(r['pnl_moyen_pct'], '{:9.1%}')}"
              f"   | {_f(b['cagr'], '{:8.1%}')}  {_f(b['max_drawdown'], '{:8.1%}')}")


def _charger(a: argparse.Namespace) -> list[dict]:
    if a.fmp:
        return [depuis_fmp(f) for f in a.fmp]
    return [depuis_yahoo(t) for t in a.yahoo]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--fmp", nargs="+", metavar="FICHIER")
    src.add_argument("--yahoo", nargs="+", metavar="TICKER")
    ap.add_argument("--debut", default="2020-01-01")
    ap.add_argument("--swing", type=int, default=50)
    ap.add_argument("--pivot", type=int, default=50)
    ap.add_argument("--modele", default="lightgbm", choices=("lightgbm", "xgboost", "logit"))
    a = ap.parse_args()
    series = _charger(a)
    res = [backtester(s, a.debut, a.swing, a.pivot) for s in series]
    imprimer(res)
    rapport_meta = meta(series, a.swing, a.pivot, a.modele)
    print(f"\nMéta-labelling : {rapport_meta['n_evenements']} événements LONG → "
          f"{rapport_meta['statut']} ({rapport_meta.get('motif')})")
    _consigner(a, res, rapport_meta)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"mesure_le": datetime.now(UTC).isoformat(timespec="seconds"),
                                  "source": "fmp" if a.fmp else "yahoo", "debut": a.debut,
                                  "swing": a.swing, "pivot": a.pivot, "actifs": res,
                                  "meta": rapport_meta}, ensure_ascii=False, indent=1,
                                 default=str), encoding="utf-8")
    chemin = SORTIE.relative_to(ROOT) if SORTIE.is_relative_to(ROOT) else SORTIE
    print(f"→ {chemin}")
    return 0


def _consigner(a: argparse.Namespace, res: list[dict], rapport_meta: dict) -> None:
    from packages.research.ledger import append_record
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"smclxtp_backtest:{a.swing}:{a.pivot}", "statut": "mesure",
                   "these": "SMCLXTP-A LONG→TP, titre par titre (ADR-0209).",
                   "params": {"debut": a.debut, "source": "fmp" if a.fmp else "yahoo",
                              "actifs": [r["symbole"] for r in res]},
                   "meta_statut": rapport_meta.get("statut"),
                   "source": "scripts/smclxtp_backtest.py (réel)"})


if __name__ == "__main__":
    raise SystemExit(main())
