"""Backtest PEAD small/mid-cap NET DE COÛTS + gate DSR/PBO — le vrai juge.

L'event-study a dit « le PEAD small/mid généralise » (placebo significatif). Ici on
répond à la seule question qui compte : gagne-t-on de l'argent NET de frais, et le
backtest est-il robuste (pas surajusté) ?

  make backtest-pead-smid
  python scripts/backtest_pead_smid.py --hold 21 --cost-bps 10

Étapes : prix (base/yfinance) + dates de résultats (yfinance) → portefeuille PEAD
quotidien net de coûts → Sharpe DÉFLATÉ (multiple testing) + PBO (CSCV sur grille de
configs) + sensibilité aux coûts. Promu seulement si DSR>0.5 ET PBO<0.5 ET edge net>0.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SMID = "CROX,ELF,CELH,RMBS,POWI,AAON,SPSC,ASO,BOOT,CALM,SHAK,FN"
# Grille PBO : on EXPLORE plusieurs configs → le CSCV mesure l'overfit de ce choix.
_GRID = [(h, lag, g) for h in (10, 21, 42) for lag in (1, 2) for g in (0.0, 0.02)]


def _earnings_dates(ticker: str):
    """Dates de résultats passées (yfinance). []."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).get_earnings_dates(limit=40)
        if df is None or df.empty:
            return []
        return sorted({d.date() for d in df.index.to_pydatetime()})
    except Exception:  # noqa: BLE001
        return []


def _load(tickers: list[str]):
    """{sym: bars}, {sym: earnings_dates} pour les tickers exploitables."""
    from packages.data.price_loader import load_bars
    data, earnings = {}, {}
    for tk in tickers:
        bars = load_bars(tk)
        eds = _earnings_dates(tk)
        if len(bars) >= 60 and len(eds) >= 3:
            data[tk], earnings[tk] = bars, eds
    return data, earnings


def _pbo(data: dict, earnings: dict, cost_bps: float) -> dict:
    """PBO via CSCV : matrice (jours × configs de la grille), 0 quand hors position."""
    import numpy as np

    from packages.portfolio.pbo import pbo_cscv
    from packages.strategies.pead_portfolio import pead_daily_returns
    series = []
    for h, lag, g in _GRID:
        days, rets = pead_daily_returns(data, earnings, hold=h, entry_lag=lag,
                                        min_gap=g, cost_bps=cost_bps)
        series.append(dict(zip(days, rets, strict=False)))
    all_days = sorted({d for s in series for d in s})
    if len(all_days) < 40:
        return {"available": False}
    mat = np.array([[s.get(d, 0.0) for s in series] for d in all_days])
    return pbo_cscv(mat, n_splits=10)


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest PEAD small/mid net de coûts")
    ap.add_argument("--tickers", default=_SMID)
    ap.add_argument("--hold", type=int, default=21)
    ap.add_argument("--entry-lag", type=int, default=1)
    ap.add_argument("--min-gap", type=float, default=0.0)
    ap.add_argument("--cost-bps", type=float, default=10.0, help="aller-retour bps")
    a = ap.parse_args()
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]

    from packages.research.ledger import trial_count
    from packages.strategies.pead_portfolio import pead_daily_returns, pead_metrics

    print(f"Chargement prix + résultats pour {len(tickers)} tickers (yfinance)…")
    data, earnings = _load(tickers)
    if len(data) < 2:
        print(f"❌ trop peu de tickers exploitables ({len(data)}).")
        return 1
    print(f"  {len(data)} tickers OK : {', '.join(sorted(data))}")

    n_trials = trial_count(facteur="pead_smid") + len(_GRID)   # grille incluse
    _, rets = pead_daily_returns(data, earnings, hold=a.hold, entry_lag=a.entry_lag,
                                 min_gap=a.min_gap, cost_bps=a.cost_bps)
    base = pead_metrics(rets, n_trials=n_trials)
    if not base.get("available"):
        print(f"❌ pas assez de jours ({base.get('n', 0)}).")
        return 1

    print(f"\nBacktest PEAD small/mid · hold={a.hold}j · coût {a.cost_bps:.0f}bps · "
          f"{base['n']} jours · {n_trials} essais")
    print(f"  rendement annualisé : {base['ann_return']*100:+.1f}%")
    print(f"  Sharpe annualisé    : {base['sharpe_ann']:+.2f}")
    print(f"  win rate (jours)    : {base['win_rate']*100:.0f}%")
    print(f"  DSR (Sharpe déflaté): {base['dsr']:.3f}")

    print("\n  Sensibilité aux coûts (les small-caps coûtent cher) :")
    for c in (10.0, 20.0, 40.0):
        _, rc = pead_daily_returns(data, earnings, hold=a.hold, entry_lag=a.entry_lag,
                                   min_gap=a.min_gap, cost_bps=c)
        mc = pead_metrics(rc, n_trials=n_trials)
        if mc.get("available"):
            print(f"    {c:>4.0f} bps → ann {mc['ann_return']*100:+5.1f}%  "
                  f"Sharpe {mc['sharpe_ann']:+.2f}  DSR {mc['dsr']:.3f}")

    pbo = _pbo(data, earnings, a.cost_bps)
    pbo_v = pbo.get("pbo") if pbo.get("available") else None
    print(f"\n  PBO (CSCV, {len(_GRID)} configs) : "
          f"{pbo_v:.3f}" if pbo_v is not None else "\n  PBO : indisponible")

    from packages.research.gate import promotion_verdict
    v = promotion_verdict(dsr=base["dsr"], pbo=pbo_v, edge=base["ann_return"])
    promu = v["promoted"]
    verdict = "✅ PROMU (edge net robuste)" if promu else "❌ REJETÉ"
    print(f"\n  → {verdict}")
    if promu:
        print("  GO : DSR>0.5 ET PBO<0.5 ET edge net>0 → 1er alpha net de frais.")
    else:
        print(f"  STOP : {', '.join(v['reasons']) or 'pas tradable'}.")

    _log(a, base, pbo_v, promu)
    _note(a, base, pbo_v, promu, sorted(data))
    return 0


def _log(a, base: dict, pbo_v, promu: bool) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(), "facteur": "pead_smid",
            "classe": ["equity"], "horizon": "swing",
            "dsr": base["dsr"], "pbo": pbo_v, "sharpe": base["sharpe_ann"],
            "statut": "promu" if promu else "rejete",
            "these": f"PEAD small/mid hold={a.hold}j coût={a.cost_bps:.0f}bps : "
                     f"ann {base['ann_return']*100:+.1f}%, DSR {base['dsr']:.3f}, "
                     f"PBO {pbo_v}.",
        })
    except Exception:  # noqa: BLE001
        pass


def _note(a, base: dict, pbo_v, promu: bool, syms: list[str]) -> None:
    try:
        d = ROOT / "vault" / "10_Backtests"
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).date().isoformat()
        (d / "PEAD_smid.md").write_text(
            f"---\ntype: backtest_result\nfacteur: pead_smid\n"
            f"dsr: {base['dsr']}\npbo: {pbo_v}\nsharpe_ann: {base['sharpe_ann']}\n"
            f"ann_return: {base['ann_return']}\nstatut: "
            f"{'promu' if promu else 'rejete'}\ndate: {today}\n---\n\n"
            f"# 📊 Backtest PEAD small/mid ({today})\n\n"
            f"{len(syms)} tickers · hold {a.hold}j · coût {a.cost_bps:.0f}bps · "
            f"{base['n']} jours.\n\n"
            f"- Rendement annualisé : **{base['ann_return']*100:+.1f}%**\n"
            f"- Sharpe annualisé : **{base['sharpe_ann']:+.2f}**\n"
            f"- DSR (déflaté) : **{base['dsr']:.3f}**\n"
            f"- PBO (CSCV) : **{pbo_v}**\n\n"
            f"Verdict : **{'PROMU' if promu else 'REJETÉ'}** "
            f"({'edge net robuste' if promu else 'pas tradable net de frais'}).\n",
            encoding="utf-8")
        print("  📝 note → vault/10_Backtests/PEAD_smid.md")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
