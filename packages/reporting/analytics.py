"""Reporting de performance institutionnel — Sortino, Calmar, Alpha/Beta vs QQQ, Max Drawdown.

Encapsule **QuantStats** si disponible pour des rapports riches, mais TOUTES les métriques clés ont
un calcul PUR (numpy stdlib) déterministe et testable → fonctionne sans la lib. Deux sorties :
`to_html_snippet()` (front Next.js) et `to_markdown_summary()` (front matter YAML → coffre Obsidian).

Sépare l'ALPHA (généré par l'algo) du BETA (marché) — vision Citadel. Net de frais : on passe la
courbe du journal réel (preset_ledger / ledger-sweep), déjà nette."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

_PPY = 252  # périodes par an (daily)


def _returns(curve: list[float]) -> list[float]:
    v = [float(x) for x in (curve or []) if x is not None]
    return [v[i] / v[i - 1] - 1.0 for i in range(1, len(v)) if v[i - 1]]


def _std(x: list[float]) -> float:
    if len(x) < 2:
        return 0.0
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def _returns_apparies(a: list[float],
                      b: list[float]) -> tuple[list[float], list[float]]:
    """Rendements de deux courbes DÉJÀ restreintes aux mêmes dates, calculés ENSEMBLE.

    Calculer `_returns` séparément sur chacune romprait l'appariement dès qu'une valeur
    manque d'un seul côté (la liste raccourcit d'un cran, tout ce qui suit se décale).
    Ici une observation n'est retenue que si les deux courbes ont un prix la veille ET
    le jour même : le couple (r_portefeuille, r_marché) porte la même séance."""
    ra: list[float] = []
    rb: list[float] = []
    for i in range(1, min(len(a), len(b))):
        pa, pb, ca, cb = a[i - 1], b[i - 1], a[i], b[i]
        if None in (pa, pb, ca, cb):
            continue
        if pa and pb and pa == pa and pb == pb and ca == ca and cb == cb:
            ra.append(ca / pa - 1.0)       # NaN écarté : pas de prix, pas d'observation
            rb.append(cb / pb - 1.0)
    return ra, rb


def _alpha_beta(rr: list[float], bb: list[float],
                ppy: int) -> tuple[float, float, float]:
    """(alpha annualisé CAPM rf=0, bêta, corrélation) sur des rendements APPARIÉS."""
    k = len(rr)
    mb = sum(bb) / k
    mr = sum(rr) / k
    cov = sum((rr[i] - mr) * (bb[i] - mb) for i in range(k)) / (k - 1)
    vb = sum((x - mb) ** 2 for x in bb) / (k - 1)
    sr = _std(rr)
    beta = cov / vb if vb > 0 else 0.0
    corr = cov / (sr * math.sqrt(vb)) if sr > 0 and vb > 0 else 0.0
    return (mr - beta * mb) * ppy, beta, corr


@dataclass(frozen=True, slots=True)
class PerfMetrics:
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    alpha_annual: float | None
    beta: float | None
    corr: float | None
    n_days: int

    def to_dict(self) -> dict:
        return asdict(self)


class PerformanceAnalytics:
    """Analyse de performance à partir d'une courbe d'equity (et d'un benchmark optionnel)."""

    def __init__(self, returns: list[float], benchmark: list[float] | None = None,
                 ppy: int = _PPY, rf: float = 0.0, *,
                 paire: tuple[list[float], list[float]] | None = None,
                 alignement: str = "position") -> None:
        self.r = [float(x) for x in returns if x is not None]
        self.b = [float(x) for x in (benchmark or []) if x is not None]
        self.ppy = ppy
        self.rf = rf
        self.alignement = alignement
        if paire is None:            # legacy : appariement par la FIN (cf. from_curves)
            m = min(len(self.r), len(self.b))
            paire = (self.r[-m:] if m else [], self.b[-m:] if m else [])
        self.rr = [float(x) for x in paire[0]]
        self.bb = [float(x) for x in paire[1]]

    @classmethod
    def from_curves(cls, equity: list[float], benchmark_curve: list[float] | None = None,
                    ppy: int = _PPY, dates: list[str] | None = None,
                    benchmark_dates: list[str] | None = None) -> PerformanceAnalytics:
        """Courbes → analyse. `dates` / `benchmark_dates` apparient PAR DATE.

        CINQUIÈME OCCURRENCE DE L'EMPILEMENT POSITIONNEL (04/09). Le bêta et l'alpha
        étaient calculés sur `min(len(r), len(b))` derniers points de chaque série —
        ce qui suppose que le preset et QQQ partagent un calendrier. Ils ne le partagent
        pas : l'un suit l'univers négociable, l'autre les indices. Le dashboard publiait
        **bêta 0,037 et corrélation 0,031** pour un portefeuille long-only d'actions
        américaines, donc une contribution alpha de 1072 % — le résidu d'un bêta faux.

        Sans les deux calendriers, l'appariement reste positionnel et `attribution()` le
        DIT (`alignement: "position"`) : un chiffre publié doit porter la manière
        dont il a été obtenu, sinon rien ne distingue une mesure d'une supposition."""
        r = _returns(equity)
        if not benchmark_curve:
            return cls(r, None, ppy=ppy)
        b = _returns(benchmark_curve)
        if dates and benchmark_dates:
            from packages.backtest.panel import apparier_deux_series
            ea, ba, _d = apparier_deux_series(
                list(equity), [str(x)[:10] for x in dates],
                list(benchmark_curve), [str(x)[:10] for x in benchmark_dates])
            return cls(r, b, ppy=ppy, paire=_returns_apparies(ea, ba),
                       alignement="date")
        return cls(r, b, ppy=ppy)

    # ── métriques (pures) ───────────────────────────────────────────────
    def _max_drawdown(self) -> float:
        eq, peak, mdd = 1.0, 1.0, 0.0
        for x in self.r:
            eq *= (1 + x)
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1.0)
        return mdd

    def metrics(self) -> PerfMetrics:
        r, ppy = self.r, self.ppy
        n = len(r)
        if n < 2:
            return PerfMetrics(0, 0, 0, 0, 0, 0, 0, None, None, None, n)
        mu = sum(r) / n
        sd = _std(r)
        total = math.prod(1 + x for x in r) - 1.0
        years = n / ppy
        cagr = (1 + total) ** (1 / years) - 1.0 if years > 0 and total > -1 else 0.0
        vol = sd * math.sqrt(ppy)
        sharpe = (mu - self.rf / ppy) / sd * math.sqrt(ppy) if sd > 0 else 0.0
        # `_std` retranche la moyenne : c'est une dispersion, pas une amplitude.
        # Mesuré le 04/09 : Sortino gonflé de 19,1 %. Définition unique ci-dessous.
        from packages.portfolio.deviation import deviation_baissiere
        downside = deviation_baissiere(r)
        sortino = (mu / downside * math.sqrt(ppy)) if downside > 0 else 0.0
        mdd = self._max_drawdown()
        calmar = (cagr / abs(mdd)) if mdd < 0 else 0.0
        alpha = beta = corr = None
        # `self.rr` / `self.bb` sont APPARIÉS (par date si les calendriers existent).
        # Ne jamais retomber ici sur `r` complet : ce mélange produisait le bêta faux.
        if len(self.rr) >= 20 and len(self.rr) == len(self.bb):
            alpha, beta, corr = _alpha_beta(self.rr, self.bb, ppy)
        return PerfMetrics(round(total, 4), round(cagr, 4), round(vol, 4), round(sharpe, 2),
                           round(sortino, 2), round(calmar, 2), round(mdd, 4),
                           None if alpha is None else round(alpha, 4),
                           None if beta is None else round(beta, 3),
                           None if corr is None else round(corr, 3), n)

    def attribution(self) -> dict[str, Any]:
        """Décompose le rendement total en contribution BÊTA (marché, QQQ) et ALPHA (généré par
        l'algo) — vision Citadel. β·r_marché = part marché ; le reste = alpha + sélection. Pur."""
        m = self.metrics()
        if not self.b:
            return {"available": False, "motif": "aucun benchmark"}
        if m.beta is None:
            return {"available": False, "alignement": self.alignement,
                    "n_observations": len(self.rr),
                    "motif": "moins de 20 séances communes "
                             "entre le portefeuille et le benchmark"}
        rr, bb = self.rr, self.bb
        k = len(rr)
        beta = m.beta
        bench_total = math.prod(1 + x for x in bb) - 1.0          # rendement marché (QQQ)
        port_total = math.prod(1 + x for x in rr) - 1.0
        beta_contrib = beta * bench_total                         # part expliquée par l'exposition marché
        alpha_contrib = port_total - beta_contrib                # résidu = rendement hors-QQQ
        share = (abs(alpha_contrib) / (abs(alpha_contrib) + abs(beta_contrib))
                 if (abs(alpha_contrib) + abs(beta_contrib)) > 0 else 0.0)
        # Significativité de l'alpha (honnêteté) : t-stat du résidu e = r - β·b.
        # « alpha » mono-facteur = COMPÉTENCE seulement si |t|≥2 ; sinon rendement
        # non corrélé à QQQ (autres bêtas + chance). Cohérent avec DSR≈0.
        resid = [rr[i] - beta * bb[i] for i in range(k)]
        mean_e = sum(resid) / k
        se = _std(resid) / math.sqrt(k) if k > 1 else 0.0
        alpha_t = mean_e / se if se > 0 else 0.0
        significant = abs(alpha_t) >= 2.0
        underperf = port_total < bench_total
        if share >= 0.5 and significant and not underperf:
            verdict = "alpha dominant (significatif)"
        elif share >= 0.5:
            verdict = "rendement hors-QQQ — NON prouvé (alpha non significatif / DSR≈0)"
        else:
            verdict = "bêta dominant (marché)"
        return {"available": True, "beta": round(beta, 3),
                "alignement": self.alignement, "n_observations": k,
                "portfolio_return": round(port_total, 4), "benchmark_return": round(bench_total, 4),
                "beta_contribution": round(beta_contrib, 4), "alpha_contribution": round(alpha_contrib, 4),
                "alpha_share": round(share, 3), "alpha_annual": m.alpha_annual,
                "alpha_tstat": round(alpha_t, 2), "alpha_significant": significant,
                "underperforms_benchmark": underperf, "verdict": verdict}

    # ── sorties ─────────────────────────────────────────────────────────
    def to_markdown_summary(self, title: str = "Performance") -> str:
        m = self.metrics()
        fm = ["---", "type: performance_report", f"date: {datetime.now(timezone.utc).date().isoformat()}",
              f"sharpe: {m.sharpe}", f"sortino: {m.sortino}", f"calmar: {m.calmar}",
              f"max_drawdown: {m.max_drawdown}",
              f"alpha_annual: {m.alpha_annual if m.alpha_annual is not None else 'null'}",
              f"beta: {m.beta if m.beta is not None else 'null'}", "tags: [quant, performance]", "---"]
        def pct(x: float | None) -> str:
            return "—" if x is None else f"{x*100:.1f}%"
        body = ["", f"# 📊 {title}", "",
                "| Métrique | Valeur |", "|---|--:|",
                f"| Rendement total | {pct(m.total_return)} |", f"| CAGR | {pct(m.cagr)} |",
                f"| Sharpe | {m.sharpe} |", f"| Sortino | {m.sortino} |", f"| Calmar | {m.calmar} |",
                f"| Max Drawdown | {pct(m.max_drawdown)} |", f"| Vol annualisée | {pct(m.vol)} |",
                f"| **Alpha annualisé** (vs QQQ) | {pct(m.alpha_annual)} |",
                f"| Beta (vs QQQ) | {m.beta if m.beta is not None else '—'} |",
                f"| Corrélation QQQ | {m.corr if m.corr is not None else '—'} |", ""]
        return "\n".join(fm + body)

    def to_html_snippet(self, title: str = "Performance") -> str:
        m = self.metrics()
        def pct(x: float | None) -> str:
            return "—" if x is None else f"{x*100:.1f}%"
        rows = [("Rendement total", pct(m.total_return)), ("CAGR", pct(m.cagr)), ("Sharpe", str(m.sharpe)),
                ("Sortino", str(m.sortino)), ("Calmar", str(m.calmar)), ("Max Drawdown", pct(m.max_drawdown)),
                ("Alpha annualisé", pct(m.alpha_annual)), ("Beta QQQ", str(m.beta if m.beta is not None else "—"))]
        trs = "".join(f'<tr><td>{k}</td><td style="text-align:right">{v}</td></tr>' for k, v in rows)
        return (f'<table class="perf"><caption>{title}</caption>'
                f"<tbody>{trs}</tbody></table>")
