"""Facteurs fondamentaux value & quality → s'enregistrent dans le registre du ranking.

Normalisés sector-neutral par le moteur (un PER/EV-EBITDA se juge vs son secteur).
Lisent ctx.fundamentals ; renvoient NaN pour les actifs sans fondamental (crypto,
forex, commodities) → le moteur les retire proprement pour ces classes.
"""

from __future__ import annotations

from packages.ranking.factors import FactorContext, factor_calcs
from packages.fundamentals import ratios, valuation


@factor_calcs.register("value")
class ValueFactor:
    """Cherté inversée : earnings yield + FCF yield + EBITDA/EV (haut = bon marché)."""
    name = "value"
    sector_neutral = True

    def values(self, ctx: FactorContext) -> dict[str, float]:
        out = {}
        funds = ctx.fundamentals or {}
        for sym in ctx.panel:
            f = funds.get(sym)
            if f is None:
                out[sym] = float("nan")
                continue
            ey = valuation.earnings_yield(f)
            fy = valuation.fcf_yield(f)
            eev = 1.0 / valuation.ev_ebitda(f) if valuation.ev_ebitda(f) else 0.0
            vals = [v for v in (ey, fy, eev) if v == v]
            out[sym] = sum(vals) / len(vals) if vals else float("nan")
        return out


@factor_calcs.register("quality")
class QualityFactor:
    """Qualité : ROIC + marge brute + conversion FCF − levier (net debt/EBITDA)."""
    name = "quality"
    sector_neutral = True

    def values(self, ctx: FactorContext) -> dict[str, float]:
        out = {}
        funds = ctx.fundamentals or {}
        for sym in ctx.panel:
            f = funds.get(sym)
            if f is None:
                out[sym] = float("nan")
                continue
            score = (ratios.roic(f) + ratios.gross_margin(f) + ratios.fcf_conversion(f)
                     - 0.1 * ratios.net_debt_to_ebitda(f))
            out[sym] = score
        return out
