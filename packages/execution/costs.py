"""Modèle de coûts réalistes : frais (bps) + slippage (bps). Dès le backtest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    fee_bps: float = 5.0       # commission
    slippage_bps: float = 2.0  # impact/spread

    def apply_buy(self, price: float) -> float:
        return price * (1 + self.slippage_bps / 1e4)

    def apply_sell(self, price: float) -> float:
        return price * (1 - self.slippage_bps / 1e4)

    def fee(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 1e4

    @property
    def round_trip_bps(self) -> float:
        """Coût aller-retour estimé (2× frais + 2× slippage), en points de base."""
        return 2 * (self.fee_bps + self.slippage_bps)

    @classmethod
    def for_asset_class(cls, asset_class: str) -> "CostModel":
        """Coûts calibrés par classe d'actifs (frais + spread/impact réalistes).

        Actions/ETF liquides ≈ faibles ; crypto/forex spreads plus larges ; commodités/indices
        via futures intermédiaires. Valeurs prudentes (retail), surchargeable par config.
        """
        return cls(**_COST_BY_CLASS.get((asset_class or "equity").lower(), _COST_BY_CLASS["equity"]))


# Hypothèses de coûts (bps) par classe — prudentes, pour un compte retail.
_COST_BY_CLASS: dict[str, dict[str, float]] = {
    "equity": {"fee_bps": 2.0, "slippage_bps": 3.0},
    "etf": {"fee_bps": 1.5, "slippage_bps": 2.0},
    "crypto": {"fee_bps": 10.0, "slippage_bps": 15.0},
    "forex": {"fee_bps": 1.0, "slippage_bps": 4.0},
    "commodity": {"fee_bps": 3.0, "slippage_bps": 6.0},
    "index": {"fee_bps": 2.0, "slippage_bps": 4.0},
}


def market_impact_bps(notional: float, adv_usd: float, coef: float = 10.0) -> float:
    """Impact de marché NON-LINÉAIRE (loi en racine carrée, Almgren) : coef·√(notional/ADV), en bps.

    Doubler la taille ne double pas l'impact, il croît en √. coef≈10 bps pour 100 % d'ADV (prudent).
    """
    if adv_usd <= 0 or notional <= 0:
        return 0.0
    return coef * (abs(notional) / adv_usd) ** 0.5


def stochastic_slippage_bps(base_slippage_bps: float, vol_ratio: float = 1.0,
                            beta: float = 1.5, cap: float = 8.0) -> float:
    """Slippage STOCHASTIQUE conditionnel à la volatilité du carnet (Griffin : le spread explose
    sur un choc d'actualité). slippage = base · (1 + β·max(0, vol_ratio − 1)), borné par `cap`×base.

    vol_ratio = vol réalisée récente / vol normale (≈ VIX/VIX_médian). En régime calme vol_ratio≈1
    → slippage = base ; sur un pic de news vol_ratio=3 → slippage ≈ base·(1+β·2).
    """
    mult = 1.0 + beta * max(0.0, vol_ratio - 1.0)
    return base_slippage_bps * min(cap, mult)


def cost_assumptions() -> list[dict]:
    """Table des hypothèses de coûts par classe (pour affichage UI / transparence TCA)."""
    return [{"asset_class": ac, "fee_bps": v["fee_bps"], "slippage_bps": v["slippage_bps"],
             "round_trip_bps": 2 * (v["fee_bps"] + v["slippage_bps"])}
            for ac, v in _COST_BY_CLASS.items()]
